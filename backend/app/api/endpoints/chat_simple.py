"""Simple chat endpoint for testing."""

import logging
import os
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from the correct path
backend_dir = Path(__file__).parent.parent.parent.parent  # Go up to backend directory
env_path = backend_dir / ".env"
load_dotenv(env_path)
logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize OpenAI client
openai_client = None
use_openai = os.getenv("USE_OPENAI_FALLBACK")
api_key = os.getenv("OPENAI_API_KEY")

logger.info(f"🔍 Debug - ENV file path: {env_path}")
logger.info(f"🔍 Debug - ENV file exists: {env_path.exists()}")
logger.info(f"🔍 Debug - USE_OPENAI_FALLBACK: '{use_openai}'")
logger.info(f"🔍 Debug - OPENAI_API_KEY exists: {bool(api_key)}")
if api_key:
    logger.info(f"🔍 Debug - API_KEY starts with: {api_key[:10]}...")

if use_openai == "true" and api_key:
    try:
        openai_client = OpenAI(api_key=api_key)
        logger.info("✅ OpenAI client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize OpenAI client: {e}")
else:
    logger.warning(f"⚠️ OpenAI client not initialized - USE_OPENAI_FALLBACK: '{use_openai}', API_KEY exists: {bool(api_key)}")


class ChatMessage(BaseModel):
    """Chat message model."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str | None = None


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    conversation_history: List[ChatMessage] = []
    model: str = "gpt-4"
    context: Dict[str, Any] | None = Field(default=None, description="Optional conversation summary payload")


class ChatResponse(BaseModel):
    """Chat response model."""
    message: ChatMessage
    model: str
    usage: Dict[str, Any] | None = None


@router.post("/", response_model=ChatResponse)
async def chat_completion(request: ChatRequest) -> ChatResponse:
    """Process chat completion request."""
    try:
        logger.info(f"Received chat request: message='{request.message}', history_length={len(request.conversation_history)}")
        
        if not openai_client:
            # Fallback response if OpenAI is not available
            response_content = "I'm currently running in mock mode. Please configure OpenAI API key for AI responses."
        else:
            # Build conversation history for OpenAI
            messages = []
            
            # Add system message for Azure Architect context
            messages.append({
                "role": "system",
                "content": """You are an expert Azure Architect AI assistant. You help users design cloud architectures, generate Infrastructure as Code (Bicep/Terraform), analyze diagrams, and provide Azure best practices.

When designing Azure architectures, ALWAYS structure your response using proper Azure hierarchy:
- Start with Management Groups (if enterprise-scale)
- Then Subscriptions
- Then Landing Zones (e.g., "Online Landing Zone", "Corp Landing Zone")
- Then Virtual Networks and Subnets
- Then specific Azure services within those networks

IMPORTANT: When listing services, use this structured format to ensure proper visual nesting:

**GROUPS:**
- Management Groups: [Management Group name]
  - Contains: [Subscription names]
- Subscriptions: [Subscription name]
  - Contains: [Landing Zone names or direct services]
- Landing Zones: [Landing Zone name] (e.g., "Online Landing Zone", "Corp Landing Zone")
  - Contains: [VNet names or services]
- Virtual Networks: [VNet name]
  - Contains: [Subnet names or services]
- Subnets: [Subnet name]
  - Contains: [Service names]

**SERVICES:**
List all Azure services with their full names (e.g., "Azure Application Gateway", "Azure Key Vault", "Azure SQL Database", "Azure Storage Account").

**CONNECTIONS:**
Describe connections between services (e.g., "App Gateway -> App Service", "App Service -> SQL Database").

Be helpful, accurate, and concise in your responses."""
            })
            
            # Inject high-level context summary if provided
            supplemental_context: List[str] = []
            if request.context:
                summary = request.context.get("summary") if isinstance(request.context, dict) else None
                recent = request.context.get("recent_messages") if isinstance(request.context, dict) else None
                if isinstance(summary, str) and summary.strip():
                    supplemental_context.append(f"Conversation summary:\n{summary.strip()}")
                if isinstance(recent, list):
                    formatted_recent = []
                    for entry in recent[-8:]:
                        if not isinstance(entry, dict):
                            continue
                        role = entry.get("role", "user")
                        content = entry.get("content", "")
                        if isinstance(content, str) and content.strip():
                            formatted_recent.append(f"{role}: {content.strip()}")
                    if formatted_recent:
                        supplemental_context.append("Recent exchanges:\n" + "\n".join(formatted_recent))
            if supplemental_context:
                messages.append({
                    "role": "system",
                    "content": "\n\n".join(supplemental_context)
                })

            # Add conversation history
            for msg in request.conversation_history:
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Add current user message
            messages.append({
                "role": "user",
                "content": request.message
            })
            
            logger.info(f"Sending {len(messages)} messages to OpenAI")
            
            # Call OpenAI API
            response = openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07"),
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )
            
            response_content = response.choices[0].message.content or "No response generated"
            logger.info(f"Received OpenAI response: {len(response_content)} characters")
        
        response_message = ChatMessage(
            role="assistant",
            content=response_content
        )
        
        return ChatResponse(
            message=response_message,
            model=request.model,
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}
        )
        
    except Exception as e:
        logger.error(f"Chat completion failed: {e}")
        raise HTTPException(status_code=500, detail=f"Chat completion failed: {str(e)}")


@router.get("/models")
async def list_models() -> Dict[str, List[str]]:
    """List available models."""
    return {
        "models": ["gpt-4", "gpt-3.5-turbo", "azure-gpt-4"]
    }
