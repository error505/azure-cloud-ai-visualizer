"""
Local Model Client for Ollama and Microsoft Foundry Local

This module provides a unified interface for local AI models, supporting:
- Ollama (local model server)
- Microsoft Foundry Local (on-device AI)

Configuration via environment variables:
- USE_OLLAMA=true - Enable Ollama integration
- OLLAMA_URL - Ollama server URL (default: http://localhost:11434)
- OLLAMA_MODEL - Model name (default: llama2)
- USE_FOUNDRY_LOCAL=true - Enable Foundry Local integration
- FOUNDRY_LOCAL_ALIAS - Model alias (default: qwen2.5-0.5b)
"""

import asyncio
import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Environment variable configuration
USE_OLLAMA = os.getenv("USE_OLLAMA", "false").lower() == "true"
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama2")

USE_FOUNDRY_LOCAL = os.getenv("USE_FOUNDRY_LOCAL", "false").lower() == "true"
FOUNDRY_LOCAL_ALIAS = os.getenv("FOUNDRY_LOCAL_ALIAS", "qwen2.5-0.5b")


class LocalModelAgentWrapper:
    """Agent wrapper compatible with AzureArchitectAgent expectations."""

    def __init__(self, model: str, instructions: str, backend: str, client_instance: Any):
        self.model = model
        self.instructions = instructions
        self.backend = backend  # "ollama" or "foundry_local"
        self._client = client_instance
        self._response_wrapper = _ResponseWrapper()

    async def run(self, prompt: str, **kwargs) -> Any:
        """
        Execute prompt and return response compatible with agent expectations.
        Returns object with .result or .text attribute, or string.
        """
        try:
            if self.backend == "ollama":
                return await self._run_ollama(prompt, **kwargs)
            elif self.backend == "foundry_local":
                return await self._run_foundry_local(prompt, **kwargs)
            else:
                raise ValueError(f"Unsupported backend: {self.backend}")
        except Exception as e:
            logger.exception(f"LocalModel run error ({self.backend}): %s", e)
            return _ResponseWrapper(text=f"ERROR: {e}")

    async def _run_ollama(self, prompt: str, **kwargs) -> Any:
        """Execute prompt using Ollama HTTP API."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for Ollama. Install with: pip install httpx")

        full_prompt = f"{self.instructions}\n\nUser: {prompt}"
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            **kwargs
        }

        url = f"{OLLAMA_URL}/api/generate"
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                
                # Ollama response format: {"response": "text", "done": true}
                text = data.get("response", "")
                if not text:
                    text = json.dumps(data)
                
                return _ResponseWrapper(text=text)
            except Exception as e:
                logger.error(f"Ollama API error: {e}")
                return _ResponseWrapper(text=f"Ollama error: {e}")

    async def _run_foundry_local(self, prompt: str, **kwargs) -> Any:
        """Execute prompt using Microsoft Foundry Local."""
        try:
            import openai
            from foundry_local import FoundryLocalManager
        except ImportError:
            raise ImportError(
                "foundry-local-sdk and openai are required. "
                "Install with: pip install foundry-local-sdk openai"
            )

        # Initialize Foundry Local manager (cached in self._client if already initialized)
        if not hasattr(self._client, 'foundry_manager'):
            logger.info(f"Initializing Foundry Local with alias: {FOUNDRY_LOCAL_ALIAS}")
            self._client.foundry_manager = FoundryLocalManager(FOUNDRY_LOCAL_ALIAS)
            self._client.openai_client = openai.OpenAI(
                base_url=self._client.foundry_manager.endpoint,
                api_key=self._client.foundry_manager.api_key
            )

        manager = self._client.foundry_manager
        openai_client = self._client.openai_client

        # Construct messages with proper typing for OpenAI SDK
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": prompt}
        ]

        try:
            response = openai_client.chat.completions.create(
                model=manager.get_model_info(FOUNDRY_LOCAL_ALIAS).id,  # type: ignore[union-attr]
                messages=messages,  # type: ignore[arg-type]
                stream=False,
                **kwargs
            )
            text = response.choices[0].message.content
            return _ResponseWrapper(text=text or "")
        except Exception as e:
            logger.error(f"Foundry Local error: {e}")
            return _ResponseWrapper(text=f"Foundry Local error: {e}")

    async def run_stream(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """
        Stream response chunks.
        Yields text chunks compatible with agent streaming expectations.
        """
        try:
            if self.backend == "ollama":
                async for chunk in self._stream_ollama(prompt, **kwargs):
                    yield chunk
            elif self.backend == "foundry_local":
                async for chunk in self._stream_foundry_local(prompt, **kwargs):
                    yield chunk
            else:
                yield f"ERROR: Unsupported backend {self.backend}"
        except Exception as e:
            logger.exception(f"LocalModel stream error ({self.backend}): %s", e)
            yield f"[ERROR] {e}"

    async def _stream_ollama(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """Stream from Ollama API."""
        try:
            import httpx
        except ImportError:
            yield "ERROR: httpx required for Ollama streaming"
            return

        full_prompt = f"{self.instructions}\n\nUser: {prompt}"
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": True,
            **kwargs
        }

        url = f"{OLLAMA_URL}/api/generate"
        
        async with httpx.AsyncClient(timeout=None) as client:
            try:
                async with client.stream("POST", url, json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            data = json.loads(line)
                            chunk_text = data.get("response", "")
                            if chunk_text:
                                yield chunk_text
                        except json.JSONDecodeError:
                            continue
            except Exception as e:
                logger.error(f"Ollama streaming error: {e}")
                yield f"[Ollama stream error: {e}]"

    async def _stream_foundry_local(self, prompt: str, **kwargs) -> AsyncGenerator[str, None]:
        """Stream from Microsoft Foundry Local."""
        try:
            import openai
            from foundry_local import FoundryLocalManager
        except ImportError:
            yield "ERROR: foundry-local-sdk and openai required"
            return

        # Initialize if needed
        if not hasattr(self._client, 'foundry_manager'):
            logger.info(f"Initializing Foundry Local with alias: {FOUNDRY_LOCAL_ALIAS}")
            self._client.foundry_manager = FoundryLocalManager(FOUNDRY_LOCAL_ALIAS)
            self._client.openai_client = openai.OpenAI(
                base_url=self._client.foundry_manager.endpoint,
                api_key=self._client.foundry_manager.api_key
            )

        manager = self._client.foundry_manager
        openai_client = self._client.openai_client

        # Construct messages with proper typing for OpenAI SDK
        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": self.instructions},
            {"role": "user", "content": prompt}
        ]

        try:
            stream = openai_client.chat.completions.create(
                model=manager.get_model_info(FOUNDRY_LOCAL_ALIAS).id,  # type: ignore[union-attr]
                messages=messages,  # type: ignore[arg-type]
                stream=True,
                **kwargs
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"Foundry Local streaming error: {e}")
            yield f"[Foundry Local stream error: {e}]"


class _ResponseWrapper:
    """Wrapper to provide .result and .text attributes expected by agent code."""
    
    def __init__(self, text: str = ""):
        self.text = text
        self.result = text
    
    def __str__(self):
        return self.text


class LocalModelClient:
    """
    Unified client for local AI models.
    
    Auto-detects backend based on environment variables:
    - USE_OLLAMA=true -> Use Ollama
    - USE_FOUNDRY_LOCAL=true -> Use Microsoft Foundry Local
    
    Provides create_agent() compatible with AzureArchitectAgent.
    """

    def __init__(self):
        self.backend = self._detect_backend()
        self.model = self._get_model_name()
        self._instance = None  # Shared instance for backend-specific clients
        
        logger.info(f"LocalModelClient initialized: backend={self.backend}, model={self.model}")

    def _detect_backend(self) -> str:
        """Detect which backend to use based on environment variables."""
        if USE_FOUNDRY_LOCAL:
            return "foundry_local"
        elif USE_OLLAMA:
            return "ollama"
        else:
            raise ValueError(
                "No local model backend enabled. "
                "Set USE_OLLAMA=true or USE_FOUNDRY_LOCAL=true"
            )

    def _get_model_name(self) -> str:
        """Get model name/alias based on backend."""
        if self.backend == "ollama":
            return OLLAMA_MODEL
        elif self.backend == "foundry_local":
            return FOUNDRY_LOCAL_ALIAS
        return "unknown"

    def create_agent(
        self, 
        name: str, 
        instructions: str, 
        tools: Optional[list] = None
    ) -> LocalModelAgentWrapper:
        """
        Create agent wrapper compatible with AzureArchitectAgent expectations.
        
        Args:
            name: Agent name (for logging)
            instructions: System instructions/prompt
            tools: Tools list (currently ignored for local models)
        
        Returns:
            LocalModelAgentWrapper with run() and run_stream() methods
        """
        logger.info(f"Creating local model agent '{name}' with backend={self.backend}")
        
        # Note: Tools are not yet supported for local models
        # Future enhancement: implement tool calling for compatible backends
        if tools:
            logger.warning(f"Tools provided but not yet supported for {self.backend} backend")
        
        # Create shared instance holder for backend-specific state
        if self._instance is None:
            self._instance = type('Instance', (), {})()
        
        return LocalModelAgentWrapper(
            model=self.model,
            instructions=instructions,
            backend=self.backend,
            client_instance=self._instance
        )


def get_local_model_client() -> Optional[LocalModelClient]:
    """
    Factory function to create LocalModelClient if local models are enabled.
    
    Returns:
        LocalModelClient instance if USE_OLLAMA or USE_FOUNDRY_LOCAL is true,
        None otherwise.
    """
    if USE_OLLAMA or USE_FOUNDRY_LOCAL:
        try:
            return LocalModelClient()
        except Exception as e:
            logger.error(f"Failed to initialize LocalModelClient: {e}")
            return None
    return None
