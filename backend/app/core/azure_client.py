"""Azure client manager for centralized Azure service access."""

import logging
from typing import Optional, Union

from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient
from azure.ai.projects.aio import AIProjectClient
from agent_framework.azure import AzureAIAgentClient
from openai import AsyncOpenAI
from agent_framework.openai import OpenAIAssistantsClient, OpenAIChatClient

from app.core.config import settings

logger = logging.getLogger(__name__)


class AzureClientManager:
    """Manages Azure service clients with proper lifecycle management."""
    
    def __init__(self) -> None:
        self.credential: Optional[DefaultAzureCredential] = None
        self.blob_client: Optional[BlobServiceClient] = None
        self.ai_project_client: Optional[AIProjectClient] = None
        self.agent_client: Optional[AzureAIAgentClient] = None
        self.openai_client: Optional[AsyncOpenAI] = None
        self.openai_assistants_client: Optional[OpenAIAssistantsClient] = None
        self.openai_chat_client: Optional[OpenAIChatClient] = None
        self._azure_architect_agent = None  # Will be AzureArchitectAgent instance
        
    async def initialize(self) -> None:
        """Initialize all Azure clients and OpenAI clients if configured."""
        logger.info("Initializing clients...")
        
        # Check for local model configuration first (highest priority)
        from app.agents.clients.local_model_client import get_local_model_client
        local_client = get_local_model_client()
        
        if local_client:
            # Use local models (Ollama or Foundry Local)
            logger.info(f"Using local model backend: {local_client.backend}")
            from app.agents.azure_architect_agent import AzureArchitectAgent
            self._azure_architect_agent = AzureArchitectAgent(agent_client=local_client)
            logger.info(f"Local model client initialized: {local_client.backend} with model {local_client.model}")
        # Prefer explicit OpenAI fallback when configured via flag or API key.
        elif settings.USE_OPENAI_FALLBACK or bool(settings.OPENAI_API_KEY):
            # Initialize OpenAI clients
            self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            # Some wrappers require a model id at construction time; pass the
            # configured OPENAI_MODEL from settings to be explicit.
            self.openai_assistants_client = OpenAIAssistantsClient(
                openai_client=self.openai_client,
                model_id=settings.OPENAI_MODEL,
            )
            self.openai_chat_client = OpenAIChatClient(
                model_id=settings.OPENAI_MODEL,
                api_key=settings.OPENAI_API_KEY,
            )
            
            # Initialize Azure Architect Agent with OpenAI client
            from app.agents.azure_architect_agent import AzureArchitectAgent
            self._azure_architect_agent = AzureArchitectAgent(
                agent_client=self.openai_chat_client  # Use chat client for true token streaming
            )
            logger.info("OpenAI clients initialized successfully (fallback)")
        else:
            # Initialize Azure credential
            self.credential = DefaultAzureCredential()
            
            # Initialize Blob Storage client
            blob_url = f"https://{settings.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net"
            self.blob_client = BlobServiceClient(
                account_url=blob_url,
                credential=self.credential
            )
            
            # Initialize AI Project client
            self.ai_project_client = AIProjectClient(
                endpoint=settings.AZURE_AI_PROJECT_ENDPOINT,
                credential=self.credential
            )
            
            # Initialize Agent client for MAF
            self.agent_client = AzureAIAgentClient(
                project_endpoint=settings.AZURE_AI_PROJECT_ENDPOINT,
                model_deployment_name=settings.AZURE_AI_MODEL_DEPLOYMENT_NAME,
                credential=self.credential
            )
            
            # Initialize Azure Architect Agent with Azure clients
            from app.agents.azure_architect_agent import AzureArchitectAgent
            self._azure_architect_agent = AzureArchitectAgent(agent_client=self.agent_client)
            logger.info("Azure clients initialized successfully")
        
        # Initialize the agent
        if self._azure_architect_agent:
            await self._azure_architect_agent.initialize()
        
        logger.info("Client initialization complete")
        
    async def cleanup(self) -> None:
        """Clean up Azure and OpenAI clients."""
        logger.info("Cleaning up clients...")
        
        if self.blob_client:
            await self.blob_client.close()
        if self.ai_project_client:
            await self.ai_project_client.close()
        if self.credential:
            await self.credential.close()
        if self.openai_client:
            await self.openai_client.close()
            
        logger.info("Clients cleaned up")
    
    async def ensure_containers_exist(self) -> None:
        """Ensure required blob containers exist."""
        if not self.blob_client:
            raise RuntimeError("Blob client not initialized")
            
        containers = [
            settings.AZURE_STORAGE_CONTAINER_NAME_PROJECTS,
            settings.AZURE_STORAGE_CONTAINER_NAME_ASSETS,
            settings.AZURE_STORAGE_CONTAINER_NAME_EXPORTS,
            settings.AZURE_STORAGE_CONTAINER_NAME_IAC,
            settings.AZURE_STORAGE_CONTAINER_NAME_DEPLOYMENTS,
            settings.AZURE_STORAGE_CONTAINER_NAME_CONVERSATIONS,
        ]
        
        for container_name in containers:
            try:
                await self.blob_client.create_container(container_name)
                logger.info(f"Created container: {container_name}")
            except Exception as e:
                if "ContainerAlreadyExists" not in str(e):
                    logger.warning(f"Failed to create container {container_name}: {e}")
                    
    def get_blob_client(self) -> BlobServiceClient:
        """Get the blob storage client."""
        if not self.blob_client:
            raise RuntimeError("Blob client not initialized")
        return self.blob_client
    
    def get_ai_project_client(self) -> AIProjectClient:
        """Get the AI project client."""
        if not self.ai_project_client:
            raise RuntimeError("AI project client not initialized")
        return self.ai_project_client
    
    def get_agent_client(self) -> AzureAIAgentClient:
        """Get the MAF agent client."""
        if not self.agent_client:
            raise RuntimeError("Agent client not initialized")
        return self.agent_client
    
    def get_openai_client(self) -> Optional[AsyncOpenAI]:
        """Get the OpenAI client."""
        return self.openai_client
    
    def get_openai_assistants_client(self) -> Optional[OpenAIAssistantsClient]:
        """Get the OpenAI Assistants client."""
        return self.openai_assistants_client
    
    def get_openai_chat_client(self) -> Optional[OpenAIChatClient]:
        """Get the OpenAI Chat client."""
        return self.openai_chat_client
    
    def get_azure_architect_agent(self):
        """Get the Azure Architect Agent."""
        if not self._azure_architect_agent:
            raise RuntimeError("Azure Architect Agent not initialized")
        return self._azure_architect_agent