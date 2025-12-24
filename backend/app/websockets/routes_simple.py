"""WebSocket routes with OpenAI integration."""

import json
import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.logger import logger as fastapi_logger
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
backend_dir = Path(__file__).parent.parent.parent.parent
env_path = backend_dir / ".env"
load_dotenv(env_path)

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
fastapi_logger.setLevel(logging.DEBUG)

router = APIRouter()

# Initialize OpenAI client for WebSocket
openai_client = None
use_openai = os.getenv("USE_OPENAI_FALLBACK")
api_key = os.getenv("OPENAI_API_KEY")

if use_openai == "true" and api_key:
    try:
        openai_client = OpenAI(api_key=api_key)
        logger.info("✅ WebSocket OpenAI client initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize WebSocket OpenAI client: {e}")
else:
    logger.warning("⚠️ WebSocket OpenAI client not initialized")

# Debug: Log when the router is created
logger.info("WebSocket router created with OpenAI integration")

# Simple connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        try:
            logger.debug(f"🤝 Accepting WebSocket for client {client_id}")
            await websocket.accept()
            logger.debug(f"✅ WebSocket accepted for client {client_id}")
            self.active_connections[client_id] = websocket
            logger.info(f"🎉 Client {client_id} connected successfully! Active connections: {len(self.active_connections)}")
        except Exception as e:
            logger.error(f"❌ Failed to accept WebSocket for client {client_id}: {e}")
            raise
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} disconnected")
    
    async def send_personal_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

manager = ConnectionManager()


@router.websocket("/chat/{client_id}")
async def websocket_chat_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time chat."""
    logger.debug(f"🔗 WebSocket connection attempt from client {client_id}")
    logger.debug(f"📋 WebSocket headers: {dict(websocket.headers)}")
    logger.debug(f"🌐 WebSocket client info: {websocket.client}")
    logger.debug(f"📍 WebSocket URL: {websocket.url}")
    
    try:
        logger.debug(f"🤝 Attempting to accept WebSocket connection for {client_id}")
        await manager.connect(websocket, client_id)
        logger.debug(f"✅ WebSocket connection accepted for {client_id}")
    except Exception as e:
        logger.error(f"❌ Failed to accept WebSocket connection for {client_id}: {e}")
        raise
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            user_content = message_data.get('content', 'No message')
            logger.info(f"📤 WebSocket received: {user_content}")
            
            # Use OpenAI API if available, otherwise fallback
            if not openai_client:
                response_content = "I'm currently running in WebSocket mock mode. Please configure OpenAI API key for AI responses."
            else:
                try:
                    # Build messages for OpenAI (similar to REST API)
                    messages = [
                        {
                            "role": "system",
                            "content": "You are an expert Azure Architect AI assistant. You help users design cloud architectures, generate Infrastructure as Code (Bicep/Terraform), analyze diagrams, and provide Azure best practices. Be helpful, accurate, and concise in your responses."
                        },
                        {
                            "role": "user",
                            "content": user_content
                        }
                    ]
                    
                    logger.info(f"🤖 Calling OpenAI API via WebSocket for: {user_content[:50]}...")
                    
                    # Call OpenAI API
                    openai_response = openai_client.chat.completions.create(
                        model=os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07"),
                        messages=messages,
                        max_tokens=1000,
                        temperature=0.7
                    )
                    
                    response_content = openai_response.choices[0].message.content or "No response generated"
                    logger.info(f"✅ OpenAI response received via WebSocket: {len(response_content)} characters")
                    
                except Exception as e:
                    logger.error(f"❌ OpenAI API error in WebSocket: {e}")
                    response_content = f"Sorry, I encountered an error processing your request: {str(e)}"
            
            response = {
                "type": "message",
                "content": response_content,
                "client_id": client_id
            }
            
            await manager.send_personal_message(json.dumps(response), client_id)
            
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        manager.disconnect(client_id)


@router.websocket("/chat")
async def websocket_chat_endpoint_auto_id(websocket: WebSocket):
    """WebSocket endpoint for real-time chat with auto-generated client ID."""
    logger.debug("🔗 WebSocket connection attempt to /chat (auto-ID)")
    logger.debug(f"📋 WebSocket headers: {dict(websocket.headers)}")
    logger.debug(f"🌐 WebSocket client info: {websocket.client}")
    client_id = str(uuid4())
    logger.debug(f"🆔 Generated client ID: {client_id}")
    await websocket_chat_endpoint(websocket, client_id)


@router.websocket("/deployment/{client_id}")
async def websocket_deployment_endpoint(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for real-time deployment monitoring."""
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            # Simple deployment status response
            response = {
                "type": "deployment_status",
                "status": "in_progress",
                "message": "Deployment started",
                "client_id": client_id
            }
            
            await manager.send_personal_message(json.dumps(response), client_id)
            
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        manager.disconnect(client_id)