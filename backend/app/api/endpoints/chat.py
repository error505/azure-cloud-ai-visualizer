"""Chat endpoints for MAF agent interaction."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, Field

from app.core.azure_client import AzureClientManager
from app.utils.integration_settings import normalize_integration_settings

logger = logging.getLogger(__name__)
router = APIRouter()


class ChatMessage(BaseModel):
    """Chat message model."""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: datetime = None
    
    def __init__(self, **data):
        if data.get('timestamp') is None:
            data['timestamp'] = datetime.utcnow()
        super().__init__(**data)


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    conversation_id: str | None = None
    conversation_history: List[Dict[str, Any]] | None = None
    context: Dict[str, Any] = Field(default_factory=dict)  # Can include diagram data, project info, etc.


class ChatResponse(BaseModel):
    """Chat response model."""
    message: str
    conversation_id: str
    timestamp: datetime
    suggestions: List[str] = []


class ConversationResponse(BaseModel):
    """Conversation response model."""
    id: str
    title: str
    messages: List[ChatMessage]
    created_at: datetime
    updated_at: datetime
    project_id: str | None = None


def get_azure_clients(request: Request) -> AzureClientManager:
    """Dependency to get Azure clients from app state."""
    return request.app.state.azure_clients


@router.post("/", response_model=ChatResponse)
async def send_message(
    chat_request: ChatRequest,
    project_id: str | None = None,
    azure_clients: AzureClientManager = Depends(get_azure_clients)
) -> ChatResponse:
    """Send a message to the Azure Architect Agent."""
    try:
        # Get or create conversation
        conversation_id = chat_request.conversation_id or str(uuid4())
        
        # Load existing conversation if available
        conversation_history: List[Dict[str, Any]] = []
        if chat_request.conversation_id:
            try:
                conversation = await _load_conversation(conversation_id, azure_clients)
                conversation_history = [msg.dict() for msg in conversation.messages]
            except HTTPException:
                # Conversation not found, start fresh
                pass
        if chat_request.conversation_history:
            conversation_history.extend(chat_request.conversation_history)

        # Get the agent and configure integration preferences if provided
        agent = azure_clients.get_azure_architect_agent()
        integration_settings = normalize_integration_settings(
            (chat_request.context or {}).get("integration_settings") if isinstance(chat_request.context, dict) else None
        )
        if hasattr(agent, "set_integration_preferences"):
            agent.set_integration_preferences(integration_settings)

        # Send message to agent with contextual summary/history
        response_text = await agent.chat(
            chat_request.message,
            conversation_history=conversation_history,
            context=chat_request.context or None,
        )
        
        # Create response
        now = datetime.utcnow()
        chat_response = ChatResponse(
            message=response_text,
            conversation_id=conversation_id,
            timestamp=now,
            suggestions=_generate_suggestions(response_text)
        )
        
        # Save conversation
        await _save_conversation_message(
            conversation_id,
            ChatMessage(role="user", content=chat_request.message),
            azure_clients,
            project_id
        )
        await _save_conversation_message(
            conversation_id,
            ChatMessage(role="assistant", content=response_text),
            azure_clients,
            project_id
        )
        
        logger.info(f"Processed chat message for conversation {conversation_id}")
        return chat_response
        
    except Exception as e:
        logger.error(f"Failed to process chat message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")


@router.get("/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    project_id: str | None = None,
    azure_clients: AzureClientManager = Depends(get_azure_clients)
) -> List[ConversationResponse]:
    """List all conversations."""
    try:
        blob_client = azure_clients.get_blob_client()
        container_name = "conversations"
        
        conversations = []
        async for blob in blob_client.get_container_client(container_name).list_blobs():
            if blob.name.endswith("/conversation.json"):
                try:
                    blob_data = await blob_client.get_blob_client(
                        container=container_name,
                        blob=blob.name
                    ).download_blob()
                    
                    conversation_data = json.loads(await blob_data.readall())
                    
                    # Apply project filter if specified
                    if project_id and conversation_data.get("project_id") != project_id:
                        continue
                    
                    # Convert message timestamps
                    messages = []
                    for msg_data in conversation_data.get("messages", []):
                        if isinstance(msg_data["timestamp"], str):
                            msg_data["timestamp"] = datetime.fromisoformat(msg_data["timestamp"])
                        messages.append(ChatMessage(**msg_data))
                    
                    conversation_data["messages"] = messages
                    conversations.append(ConversationResponse(**conversation_data))
                    
                except Exception as e:
                    logger.warning(f"Failed to load conversation from {blob.name}: {e}")
                    continue
        
        # Sort by updated_at descending
        conversations.sort(key=lambda c: c.updated_at, reverse=True)
        return conversations
        
    except Exception as e:
        logger.error(f"Failed to list conversations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list conversations: {str(e)}")


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    azure_clients: AzureClientManager = Depends(get_azure_clients)
) -> ConversationResponse:
    """Get a specific conversation."""
    return await _load_conversation(conversation_id, azure_clients)


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    azure_clients: AzureClientManager = Depends(get_azure_clients)
) -> Dict[str, str]:
    """Delete a conversation."""
    try:
        blob_client = azure_clients.get_blob_client()
        container_name = "conversations"
        blob_name = f"{conversation_id}/conversation.json"
        
        await blob_client.get_blob_client(
            container=container_name,
            blob=blob_name
        ).delete_blob()
        
        logger.info(f"Deleted conversation {conversation_id}")
        return {"message": "Conversation deleted successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete conversation: {str(e)}")


@router.post("/analyze-diagram", response_model=ChatResponse)
async def analyze_diagram(
    diagram_data: Dict[str, Any],
    target_region: str = "westeurope",
    conversation_id: str | None = None,
    project_id: str | None = None,
    azure_clients: AzureClientManager = Depends(get_azure_clients)
) -> ChatResponse:
    """Analyze a ReactFlow diagram using the agent."""
    try:
        # Get or create conversation
        conversation_id = conversation_id or str(uuid4())
        
        # Get the agent
        agent = azure_clients.get_azure_architect_agent()
        
        # Use the analyze_diagram tool directly
        diagram_json = json.dumps(diagram_data)
        analysis = await agent.analyze_diagram(diagram_json, target_region)
        
        now = datetime.utcnow()
        chat_response = ChatResponse(
            message=analysis,
            conversation_id=conversation_id,
            timestamp=now,
            suggestions=[
                "Generate Bicep template from this diagram",
                "Create deployment plan",
                "Suggest security improvements",
                "Optimize for cost"
            ]
        )
        
        # Save conversation
        await _save_conversation_message(
            conversation_id,
            ChatMessage(role="user", content=f"Please analyze this diagram for {target_region}"),
            azure_clients,
            project_id
        )
        await _save_conversation_message(
            conversation_id,
            ChatMessage(role="assistant", content=analysis),
            azure_clients,
            project_id
        )
        
        logger.info(f"Analyzed diagram for conversation {conversation_id}")
        return chat_response
        
    except Exception as e:
        logger.error(f"Failed to analyze diagram: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to analyze diagram: {str(e)}")


async def _load_conversation(
    conversation_id: str,
    azure_clients: AzureClientManager
) -> ConversationResponse:
    """Load conversation from blob storage."""
    try:
        blob_client = azure_clients.get_blob_client()
        container_name = "conversations"
        blob_name = f"{conversation_id}/conversation.json"
        
        blob_data = await blob_client.get_blob_client(
            container=container_name,
            blob=blob_name
        ).download_blob()
        
        conversation_data = json.loads(await blob_data.readall())
        
        # Convert message timestamps
        messages = []
        for msg_data in conversation_data.get("messages", []):
            if isinstance(msg_data["timestamp"], str):
                msg_data["timestamp"] = datetime.fromisoformat(msg_data["timestamp"])
            messages.append(ChatMessage(**msg_data))
        
        conversation_data["messages"] = messages
        return ConversationResponse(**conversation_data)
        
    except Exception as e:
        logger.error(f"Failed to load conversation {conversation_id}: {e}")
        raise HTTPException(status_code=404, detail="Conversation not found")


async def _save_conversation_message(
    conversation_id: str,
    message: ChatMessage,
    azure_clients: AzureClientManager,
    project_id: str | None = None
) -> None:
    """Save a message to conversation."""
    try:
        blob_client = azure_clients.get_blob_client()
        container_name = "conversations"
        blob_name = f"{conversation_id}/conversation.json"
        
        # Load existing conversation or create new
        try:
            blob_data = await blob_client.get_blob_client(
                container=container_name,
                blob=blob_name
            ).download_blob()
            conversation_data = json.loads(await blob_data.readall())
            
            # Convert existing message timestamps
            messages = []
            for msg_data in conversation_data.get("messages", []):
                if isinstance(msg_data["timestamp"], str):
                    msg_data["timestamp"] = datetime.fromisoformat(msg_data["timestamp"])
                messages.append(ChatMessage(**msg_data))
                
        except Exception:
            # New conversation
            now = datetime.utcnow()
            conversation_data = {
                "id": conversation_id,
                "title": _generate_conversation_title(message.content),
                "messages": [],
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "project_id": project_id
            }
            messages = []
        
        # Add new message
        messages.append(message)
        conversation_data["messages"] = [msg.dict() for msg in messages]
        conversation_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Save back to blob
        await blob_client.get_blob_client(
            container=container_name,
            blob=blob_name
        ).upload_blob(json.dumps(conversation_data, indent=2, default=str), overwrite=True)
        
    except Exception as e:
        logger.error(f"Failed to save conversation message: {e}")
        raise


def _generate_conversation_title(first_message: str) -> str:
    """Generate a title for the conversation based on the first message."""
    # Take first 50 characters and clean up
    title = first_message[:50].strip()
    if len(first_message) > 50:
        title += "..."
    
    # Remove common chat starters
    for starter in ["Please", "Can you", "How do I", "What is", "Help me"]:
        if title.startswith(starter):
            title = title[len(starter):].strip()
            break
    
    return title.capitalize() if title else "New Conversation"


def _generate_suggestions(response: str) -> List[str]:
    """Generate follow-up suggestions based on agent response."""
    suggestions = []
    
    response_lower = response.lower()
    
    if "bicep" in response_lower or "template" in response_lower:
        suggestions.append("Generate Bicep template")
    
    if "deploy" in response_lower or "resource" in response_lower:
        suggestions.append("Create deployment plan")
        
    if "security" in response_lower or "access" in response_lower:
        suggestions.append("Review security configuration")
        
    if "cost" in response_lower or "pricing" in response_lower:
        suggestions.append("Optimize for cost")
        
    if "monitor" in response_lower or "insight" in response_lower:
        suggestions.append("Add monitoring and alerts")
    
    # Default suggestions if none matched
    if not suggestions:
        suggestions = [
            "Tell me more",
            "Show me alternatives",
            "What about security?",
            "How much will this cost?"
        ]
    
    return suggestions[:4]  # Max 4 suggestions
