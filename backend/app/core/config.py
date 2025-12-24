"""Configuration settings for the Azure Architect Backend."""

from typing import Any, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )
    
    # OpenAI (fallback for easier testing)
    OPENAI_API_KEY: str | None = Field(default=None, description="OpenAI API key for fallback")
    OPENAI_MODEL: str = Field(default="gpt-4o-mini", description="OpenAI model to use (gpt-4o-mini supports true streaming)")
    USE_OPENAI_FALLBACK: bool = Field(default=False, description="Use OpenAI instead of Azure OpenAI when available")
    
    # Azure configuration (optional when using OpenAI fallback)
    AZURE_SUBSCRIPTION_ID: str | None = Field(default=None, description="Azure subscription ID")
    AZURE_TENANT_ID: str | None = Field(default=None, description="Azure tenant ID")
    AZURE_RESOURCE_GROUP: str | None = Field(default=None, description="Default resource group")
    
    # Azure AI Project (for MAF)
    AZURE_AI_PROJECT_ENDPOINT: str | None = Field(default=None, description="Azure AI project endpoint")
    AZURE_AI_MODEL_DEPLOYMENT_NAME: str = Field(default="gpt-4o-mini", description="Model deployment name")
    
    # Azure OpenAI (alternative)
    AZURE_OPENAI_ENDPOINT: str | None = Field(default=None, description="Azure OpenAI endpoint")
    AZURE_OPENAI_API_KEY: str | None = Field(default=None, description="Azure OpenAI API key")
    AZURE_OPENAI_API_VERSION: str = Field(default="2024-06-01", description="OpenAI API version")
    
    # Azure Storage (optional when using OpenAI fallback)
    AZURE_STORAGE_ACCOUNT_NAME: str | None = Field(default=None, description="Storage account name")
    AZURE_STORAGE_CONTAINER_NAME_PROJECTS: str = Field(default="projects", description="Projects container")
    AZURE_STORAGE_CONTAINER_NAME_ASSETS: str = Field(default="assets", description="Assets container")
    AZURE_STORAGE_CONTAINER_NAME_EXPORTS: str = Field(default="exports", description="Exports container")
    AZURE_STORAGE_CONTAINER_NAME_IAC: str = Field(default="iac", description="IaC templates container")
    AZURE_STORAGE_CONTAINER_NAME_DEPLOYMENTS: str = Field(default="deployments", description="Deployments container")
    AZURE_STORAGE_CONTAINER_NAME_CONVERSATIONS: str = Field(default="conversations", description="Conversations container")
    
    # Azure Key Vault
    AZURE_KEY_VAULT_URL: str | None = Field(default=None, description="Key Vault URL")
    
    # Application settings
    ENVIRONMENT: str = Field(default="development", description="Environment name")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="CORS allowed origins"
    )
    FRONTEND_BASE_URL: str = Field(default="http://localhost:8080/app", description="Frontend base URL (including path) for share links")
    
    # Chat and WebSocket
    CHAT_MAX_HISTORY: int = Field(default=50, description="Max chat history messages")
    WEBSOCKET_PING_INTERVAL: int = Field(default=30, description="WebSocket ping interval")
    
    # IaC Generation
    DEFAULT_AZURE_REGION: str = Field(default="westeurope", description="Default Azure region")
    BICEP_OUTPUT_FORMAT: str = Field(default="json", description="Bicep output format")
    TERRAFORM_VERSION: str = Field(default="1.5.0", description="Terraform version")
    
    # MCP Integration (disabled by default - enable via frontend integration settings)
    AZURE_MCP_BICEP_URL: str = Field(
        default="",
        description="Azure Bicep MCP server endpoint (leave blank to disable)"
    )
    TERRAFORM_MCP_URL: str = Field(
        default="",
        description="HashiCorp Terraform MCP server endpoint (leave blank to disable)"
    )
    MICROSOFT_LEARN_MCP_URL: str = Field(
        default="",
        description="Microsoft Learn documentation MCP endpoint (leave blank to disable)"
    )
    
    # Deployment
    DEPLOYMENT_TIMEOUT_MINUTES: int = Field(default=30, description="Deployment timeout")
    MAX_CONCURRENT_DEPLOYMENTS: int = Field(default=3, description="Max concurrent deployments")
    
    @property
    def storage_connection_string(self) -> str | None:
        """Generate storage connection string."""
        if not self.AZURE_STORAGE_ACCOUNT_NAME:
            return None
        return f"DefaultEndpointsProtocol=https;AccountName={self.AZURE_STORAGE_ACCOUNT_NAME};BlobEndpoint=https://{self.AZURE_STORAGE_ACCOUNT_NAME}.blob.core.windows.net/;AccountKey=<key_from_managed_identity>"


# Global settings instance
settings = Settings()
