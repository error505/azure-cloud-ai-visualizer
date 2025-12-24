"""Dependency management for MCP tools and other shared resources."""

import os
import logging
import time
import asyncio
from typing import Optional

try:
    import httpx
except ImportError:  # pragma: no cover
    httpx = None

logger = logging.getLogger(__name__)

# Global MCP tool instances for connection pooling
_mcp_bicep_tool: Optional[object] = None
_mcp_terraform_tool: Optional[object] = None
_microsoft_docs_mcp_tool: Optional[object] = None
_mcp_terraform_backoff_until: Optional[float] = None
_mcp_bicep_backoff_until: Optional[float] = None
_microsoft_docs_backoff_until: Optional[float] = None


async def get_mcp_bicep_tool():
    """Get or create the Azure Bicep MCP tool singleton.
    
    Opens a persistent connection to the Azure Bicep MCP server for
    schema lookups and validation during IaC generation.
    """
    global _mcp_bicep_tool, _mcp_bicep_backoff_until

    if _mcp_bicep_backoff_until and time.time() < _mcp_bicep_backoff_until:
        if _mcp_bicep_tool is None:
            logger.debug(
                "Skipping Azure Bicep MCP initialization until %.0f due to previous errors",
                _mcp_bicep_backoff_until,
            )
        return _mcp_bicep_tool
    if _mcp_bicep_tool is None:
        try:
            from app.core.config import settings
            mcp_url = (settings.AZURE_MCP_BICEP_URL or "").strip()

            # Basic guard: don't attempt to initialize when no real MCP endpoint is configured
            force_init = os.getenv("AZURE_MCP_BICEP_FORCE", "false").lower() in ("1", "true", "yes")
            if (not mcp_url or "learn.microsoft.com" in mcp_url or "docs.microsoft.com" in mcp_url) and not force_init:
                logger.info(
                    "Azure Bicep MCP URL not configured or points to docs; skipping MCP initialization.\n"
                    "If you intend to use the official learn.microsoft.com MCP endpoint, ensure your environment supports a streamable MCP HTTP transport and set AZURE_MCP_BICEP_FORCE=true to force initialization.\n"
                    "Note: Browsers and plain HTTP POSTs won't work; use MCPStreamableHTTPTool from agent_framework which establishes a streaming MCP session."
                )
                return None

            # Import MCP tool from agent framework
            from agent_framework import MCPStreamableHTTPTool

            _mcp_bicep_tool = MCPStreamableHTTPTool(
                name="Azure Bicep MCP",
                url=mcp_url,
            )

            # Open connection once and reuse
            enter_method = getattr(_mcp_bicep_tool, '__aenter__', None)
            if enter_method:
                try:
                    await enter_method()
                except (Exception, asyncio.CancelledError) as exc:  # pragma: no cover - network dependent
                    logger.warning("Failed to initialize Azure Bicep MCP tool (%s). Falling back to local generation.", exc)
                    _mcp_bicep_tool = None
                    _mcp_bicep_backoff_until = time.time() + 300
                    return None
            logger.info(f"Initialized Azure Bicep MCP tool at {mcp_url}")
            _mcp_bicep_backoff_until = None

        except ImportError:
            logger.warning("MCPStreamableHTTPTool not installed - MCP integration disabled.\n" \
                           "Install the agent_framework package that provides MCPStreamableHTTPTool to enable MCP features.")
            _mcp_bicep_tool = None
            _mcp_bicep_backoff_until = None
        except Exception as e:
            logger.error(f"Failed to initialize MCP Bicep tool: {e}")
            _mcp_bicep_tool = None
            _mcp_bicep_backoff_until = time.time() + 300
    
    return _mcp_bicep_tool


async def get_mcp_terraform_tool():
    """Get or create the HashiCorp Terraform MCP tool singleton.
    
    Opens a persistent connection to the HashiCorp Terraform MCP server for
    provider/resource schema lookups and validation during Terraform generation.
    """
    global _mcp_terraform_tool, _mcp_terraform_backoff_until

    if _mcp_terraform_backoff_until and time.time() < _mcp_terraform_backoff_until:
        if _mcp_terraform_tool is None:
            logger.debug(
                "Skipping Terraform MCP initialization until %.0f due to previous rate limiting",
                _mcp_terraform_backoff_until,
            )
        return _mcp_terraform_tool
    if _mcp_terraform_tool is None:
        try:
            from app.core.config import settings
            mcp_url = (settings.TERRAFORM_MCP_URL or "").strip()

            force_init = os.getenv("TERRAFORM_MCP_FORCE", "false").lower() in ("1", "true", "yes")
            if (not mcp_url or "developer.hashicorp.com" in mcp_url or "github.com/hashicorp" in mcp_url) and not force_init:
                logger.info(
                    "Terraform MCP URL not configured or points to docs; skipping MCP initialization.\n"
                    "If you intend to use the official HashiCorp MCP endpoint, ensure your environment supports a streamable MCP HTTP transport and set TERRAFORM_MCP_FORCE=true to force initialization.\n"
                    "Note: Browsers and plain HTTP POSTs won't work; use MCPStreamableHTTPTool from agent_framework which establishes a streaming MCP session."
                )
                return None

            # Import MCP tool from agent framework
            from agent_framework import MCPStreamableHTTPTool

            _mcp_terraform_tool = MCPStreamableHTTPTool(
                name="HashiCorp Terraform MCP",
                url=mcp_url,
            )

            # Open connection once and reuse
            enter_method = getattr(_mcp_terraform_tool, '__aenter__', None)
            if enter_method:
                await enter_method()
            logger.info(f"Initialized HashiCorp Terraform MCP tool at {mcp_url}")
            _mcp_terraform_backoff_until = None

        except ImportError:
            logger.warning("MCPStreamableHTTPTool not installed - Terraform MCP integration disabled.\n" \
                           "Install the agent_framework package that provides MCPStreamableHTTPTool to enable MCP features.")
            _mcp_terraform_tool = None
            _mcp_terraform_backoff_until = None
        except (Exception, asyncio.CancelledError) as e:
            _mcp_terraform_tool = None
            backoff_seconds = 300
            is_rate_limited = False
            if httpx is not None and isinstance(e, httpx.HTTPStatusError):
                status = getattr(e.response, "status_code", None)
                if status == 429:
                    is_rate_limited = True
            if "429" in str(e):
                is_rate_limited = True

            if is_rate_limited:
                logger.warning(
                    "Terraform MCP server returned HTTP 429 (rate limit). Falling back to local generation and sleeping for %s seconds.",
                    backoff_seconds,
                )
                _mcp_terraform_backoff_until = time.time() + backoff_seconds
            else:
                logger.error(f"Failed to initialize MCP Terraform tool: {e}")
                # Avoid hammering the endpoint repeatedly; back off briefly.
                _mcp_terraform_backoff_until = time.time() + 60

            _mcp_terraform_tool = None
    
    return _mcp_terraform_tool


async def cleanup_mcp_tools():
    """Clean up MCP tool connections on app shutdown."""
    global _mcp_bicep_tool, _mcp_terraform_tool, _microsoft_docs_mcp_tool
    
    # Clean up Bicep MCP tool
    if _mcp_bicep_tool is not None:
        try:
            cleanup_method = getattr(_mcp_bicep_tool, '__aexit__', None)
            if cleanup_method:
                await cleanup_method(None, None, None)
            logger.info("Cleaned up MCP Bicep tool connection")
        except Exception as e:
            logger.warning(f"Error cleaning up MCP Bicep tool: {e}")
        finally:
            _mcp_bicep_tool = None
    
    # Clean up Terraform MCP tool
    if _mcp_terraform_tool is not None:
        try:
            cleanup_method = getattr(_mcp_terraform_tool, '__aexit__', None)
            if cleanup_method:
                await cleanup_method(None, None, None)
            logger.info("Cleaned up MCP Terraform tool connection")
        except Exception as e:
            logger.warning(f"Error cleaning up MCP Terraform tool: {e}")
        finally:
            _mcp_terraform_tool = None

    # Clean up Microsoft Docs MCP tool
    if _microsoft_docs_mcp_tool is not None:
        try:
            cleanup_method = getattr(_microsoft_docs_mcp_tool, '__aexit__', None)
            if cleanup_method:
                await cleanup_method(None, None, None)
            logger.info("Cleaned up Microsoft Docs MCP tool connection")
        except Exception as e:
            logger.warning(f"Error cleaning up Microsoft Docs MCP tool: {e}")
        finally:
            _microsoft_docs_mcp_tool = None


async def get_microsoft_docs_mcp_tool():
    """Get or create the Microsoft Learn documentation MCP tool singleton."""
    global _microsoft_docs_mcp_tool, _microsoft_docs_backoff_until

    if _microsoft_docs_backoff_until and time.time() < _microsoft_docs_backoff_until:
        if _microsoft_docs_mcp_tool is None:
            logger.debug(
                "Skipping Microsoft Docs MCP initialization until %.0f due to previous errors",
                _microsoft_docs_backoff_until,
            )
        return _microsoft_docs_mcp_tool

    if _microsoft_docs_mcp_tool is None:
        try:
            from app.core.config import settings
            mcp_url = (settings.MICROSOFT_LEARN_MCP_URL or "").strip()

            if not mcp_url:
                logger.info("Microsoft Learn MCP URL not configured; skipping docs MCP initialization.")
                return None

            from agent_framework import MCPStreamableHTTPTool

            _microsoft_docs_mcp_tool = MCPStreamableHTTPTool(
                name="Microsoft Learn MCP",
                url=mcp_url,
            )

            enter_method = getattr(_microsoft_docs_mcp_tool, '__aenter__', None)
            if enter_method:
                try:
                    await enter_method()
                except (Exception, asyncio.CancelledError) as exc:
                    logger.warning(
                        "Failed to initialize Microsoft Docs MCP tool (%s). Continuing without documentation MCP.",
                        exc,
                    )
                    _microsoft_docs_mcp_tool = None
                    _microsoft_docs_backoff_until = time.time() + 300
                    return None

            logger.info(f"Initialized Microsoft Docs MCP tool at {mcp_url}")
            _microsoft_docs_backoff_until = None

        except ImportError:
            logger.warning("MCPStreamableHTTPTool not installed - Microsoft Docs MCP integration disabled.")
            _microsoft_docs_mcp_tool = None
            _microsoft_docs_backoff_until = None
        except Exception as e:
            logger.warning(f"Failed to initialize Microsoft Docs MCP tool: {e}")
            _microsoft_docs_mcp_tool = None
            _microsoft_docs_backoff_until = time.time() + 300

    return _microsoft_docs_mcp_tool


def get_agent_client():
    """Get the appropriate agent client for dual-pass validation and other AI agents.
    
    Priority:
    1. Local models (Ollama/AI Foundry) if USE_OLLAMA or USE_FOUNDRY_LOCAL is set
    2. OpenAI if USE_OPENAI_FALLBACK or OPENAI_API_KEY is set
    3. Azure AI if Azure credentials are configured
    
    Returns a client that supports create_agent() method.
    """
    from app.core.config import settings
    
    # Check for local model configuration first
    from app.agents.clients.local_model_client import get_local_model_client
    local_client = get_local_model_client()
    if local_client:
        logger.info(f"Using local model client for validation: {local_client.backend}")
        return local_client
    
    # Check for OpenAI fallback
    if settings.USE_OPENAI_FALLBACK or bool(settings.OPENAI_API_KEY):
        try:
            from agent_framework.openai import OpenAIChatClient
            client = OpenAIChatClient(
                model_id=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
            )
            logger.info(f"Using OpenAI client for validation: {settings.OPENAI_MODEL}")
            return client
        except Exception as e:
            logger.error(f"Failed to create OpenAI client: {e}")
    
    # Fall back to Azure AI
    try:
        from azure.identity.aio import DefaultAzureCredential
        from agent_framework.azure import AzureAIAgentClient
        
        credential = DefaultAzureCredential()
        client = AzureAIAgentClient(
            project_endpoint=settings.AZURE_AI_PROJECT_ENDPOINT,
            model_deployment_name=settings.AZURE_AI_MODEL_DEPLOYMENT_NAME,
            credential=credential
        )
        logger.info(f"Using Azure AI client for validation: {settings.AZURE_AI_MODEL_DEPLOYMENT_NAME}")
        return client
    except Exception as e:
        logger.error(f"Failed to create Azure AI client: {e}")
        raise RuntimeError(
            "No valid agent client available. Configure one of: "
            "OPENAI_API_KEY, USE_OLLAMA, or Azure AI credentials"
        )
