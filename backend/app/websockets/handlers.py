"""WebSocket handlers for real-time communication."""

import json
import logging
from typing import Dict, Any, List
from datetime import datetime
import asyncio
import contextlib
from app.obs.tracing import tracer
from app.agents.landing_zone_team import LandingZoneTeam
from fastapi import WebSocket, WebSocketDisconnect
from app.core.azure_client import AzureClientManager
from app.agents.tools.analyze_diagram import analyze_diagram
from app.utils.integration_settings import normalize_integration_settings

logger = logging.getLogger(__name__)

RAG_KEYWORDS = (
    "rag",
    "retrieval augmented",
    "vector search",
    "vector database",
    "semantic search",
    "vector index",
    "knowledge retrieval",
    "grounded ai",
    "grounded intelligence",
    "document qa",
)

RAG_IMPLEMENTATION_GUIDANCE = (
    "### Retrieval-Augmented Generation (RAG) reference blueprint\n"
    "- Model three lanes: ingestion/indexing, orchestration/runtime, and monitoring/security. Do NOT collapse them into a single box.\n"
    "- Ingestion + indexing: ingest banking documents into Azure Blob Storage or Data Lake (storage/10089-icon-service-Storage-Accounts), orchestrate pipelines with Azure Data Factory/Synapse, and run chunking/ETL via Azure Functions (compute/10029-icon-service-Function-Apps) or Azure Container Apps. Show these resources and their connections explicitly.\n"
    "- Embeddings/vector store: call Azure OpenAI (ai + machine learning/03438-icon-service-Azure-OpenAI) or Azure AI Studio to generate embeddings and persist vectors inside Azure AI Search / Cognitive Search (ai + machine learning/10044-icon-service-Cognitive-Search) configured for semantic + vector indexes. Include the index resource and its diagnostic settings.\n"
    "- Runtime/API tier: expose the RAG assistant via Azure App Service (app services/10035-icon-service-App-Services) or Functions plus Azure API Management (integration/10036-icon-service-API-Management) / Front Door. This tier must orchestrate: user prompt -> Azure AI Search vector query -> Azure OpenAI chat/completions -> response. Draw edges capturing this flow.\n"
    "- State/cache/data: include repositories for metadata or chats such as Azure SQL, Cosmos DB, or Azure Cache for Redis (databases/10137-icon-service-Cache-Redis) plus storage for reference docs. Keep Key Vault, private endpoints, Log Analytics, Defender for Cloud, and policy initiatives to satisfy fintech governance.\n"
    "- Diagram JSON MUST list these services with the official icon ids noted above, plus vnets/subnets, Key Vault, monitoring, and security guardrails. Connections should show ingestion -> embeddings -> vector index -> LLM -> app/API/channel."
)

STREAMING_AGENTS = {
    "Architect",
    "SecurityReviewer",
    "IdentityGovernanceReviewer",
    "NamingEnforcer",
    "ReliabilityReviewer",
    "CostPerfOptimizer",
    "ComplianceReviewer",
    "NetworkingReviewer",
    "ObservabilityReviewer",
    "DataStorageReviewer",
    "FinalEditor",
}


def _needs_rag_guidance(message: str | None) -> bool:
    if not message:
        return False
    text = message.lower()
    return any(keyword in text for keyword in RAG_KEYWORDS)


class ConnectionManager:
    """Manages WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.conversation_connections: Dict[str, list] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept a WebSocket connection."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client {client_id} connected")
    
    def disconnect(self, client_id: str):
        """Remove a WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} disconnected")
    
    async def send_personal_message(self, message: str, client_id: str):
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to {client_id}: {e}")
                self.disconnect(client_id)
    
    async def send_json_message(self, data: dict, client_id: str):
        """Send JSON data to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.warning(f"Failed to send to {client_id}: {e}")
                self.disconnect(client_id)
    
    def add_to_conversation(self, conversation_id: str, client_id: str):
        """Add client to conversation for broadcasting."""
        if conversation_id not in self.conversation_connections:
            self.conversation_connections[conversation_id] = []
        if client_id not in self.conversation_connections[conversation_id]:
            self.conversation_connections[conversation_id].append(client_id)
    
    async def broadcast_to_conversation(self, conversation_id: str, data: dict):
        """Broadcast message to all clients in a conversation."""
        if conversation_id in self.conversation_connections:
            clients = self.conversation_connections[conversation_id].copy()
            for client_id in clients:
                try:
                    await self.send_json_message(data, client_id)
                except Exception as e:
                    logger.warning(f"Failed to send to client {client_id}: {e}")
                    # Remove disconnected client
                    if client_id in self.conversation_connections[conversation_id]:
                        self.conversation_connections[conversation_id].remove(client_id)


# Global connection manager
manager = ConnectionManager()

# NEW: bridge TraceEvent -> WebSocket messages
async def _dispatch_trace_event(payload: Dict[str, Any], client_id: str, conversation_id: str | None):
    msg = {
        "type": "trace_event",
        "run_id": payload["run_id"],
        "step_id": payload["step_id"],
        "agent": payload["agent"],
        "phase": payload["phase"],
        "ts": payload["ts"],
        "meta": payload.get("meta", {}),
        "progress": payload.get("progress", {}),
        "telemetry": payload.get("telemetry", {}),
        "message_delta": payload.get("message_delta"),
        "summary": payload.get("summary"),
        "error": payload.get("error"),
        "conversation_id": conversation_id,
    }
    await manager.send_json_message(msg, client_id)
    if conversation_id:
        await manager.broadcast_to_conversation(conversation_id, msg)


async def _forward_agent_stream(payload: Dict[str, Any], client_id: str, conversation_id: str | None):
    agent = payload.get("agent")
    print(f"[STREAM-FORWARD] Agent: {agent}, Is in STREAMING_AGENTS: {agent in STREAMING_AGENTS}")
    if agent not in STREAMING_AGENTS:
        return
    phase = payload.get("phase")
    delta = payload.get("message_delta")
    print(f"[STREAM-FORWARD] Phase: {phase}, Delta length: {len(delta) if delta else 0}, Delta preview: {repr(delta[:50]) if delta else 'None'}")
    if not delta and phase not in ("end", "error"):
        print(f"[STREAM-FORWARD] Skipping - no delta and phase not end/error")
        return
    stream_msg = {
        "type": "agent_stream",
        "run_id": payload.get("run_id"),
        "step_id": payload.get("step_id"),
        "agent": agent,
        "phase": phase,
        "ts": payload.get("ts"),
        "message_delta": delta,
        "conversation_id": conversation_id,
    }
    print(f"[STREAM-FORWARD] Sending agent_stream message to client {client_id}")
    await manager.send_json_message(stream_msg, client_id)
    if conversation_id:
        await manager.broadcast_to_conversation(conversation_id, stream_msg)
    print(f"[STREAM-FORWARD] ✓ Sent successfully")


async def _replay_trace_log(run_id: str, client_id: str, conversation_id: str | None) -> bool:
    """Send any persisted trace backlog to the subscriber before streaming live updates."""
    replayed = False
    history: List[Dict[str, Any]] = await tracer.read_persisted(run_id)
    for payload in history:
        replayed = True
        await _dispatch_trace_event(payload, client_id, conversation_id)
        await _forward_agent_stream(payload, client_id, conversation_id)
    return replayed


async def _forward_trace_events(run_id: str, client_id: str, conversation_id: str | None):
    print(f"\n[TRACE-FORWARDER] Starting for run_id={run_id}, client_id={client_id}")
    try:
        queue = tracer.attach(run_id)
        print(f"[TRACE-FORWARDER] ✓ Attached to tracer queue")
        try:
            await _replay_trace_log(run_id, client_id, conversation_id)
            print(f"[TRACE-FORWARDER] ✓ Replay complete, starting live forwarding...")
            event_count = 0
            while True:
                raw = await queue.get()
                if raw is None:
                    print(f"[TRACE-FORWARDER] Received termination signal (None)")
                    break
                event_count += 1
                print(f"[TRACE-FORWARDER] Event {event_count}: {raw[:200]}")
                payload = json.loads(raw)
                print(f"[TRACE-FORWARDER] Event {event_count} parsed - agent: {payload.get('agent')}, phase: {payload.get('phase')}")
                await _dispatch_trace_event(payload, client_id, conversation_id)
                await _forward_agent_stream(payload, client_id, conversation_id)
            print(f"[TRACE-FORWARDER] ✓ Forwarding complete - {event_count} events processed")
        finally:
            tracer.detach(run_id, queue)
            print(f"[TRACE-FORWARDER] ✓ Detached from tracer")
    except asyncio.CancelledError:
        print(f"[TRACE-FORWARDER] Task cancelled")
        # Task cancelled when run completes; swallow cancellation so loop exits quietly
        pass


async def handle_team_stream_chat(data: dict, client_id: str, azure_clients: AzureClientManager):
    """
    Run the multi-agent 'landing zone team' with tracing and stream progress over WS.
    Expected payload:
      {
        "type": "team_stream_chat",
        "message": "Design a secure Azure landing zone for a fintech startup",
        "conversation_id": "...",
        "parallel": true    # optional: if true, uses fan-out/fan-in pass
      }
    """
    run_id: str | None = None
    forwarder: asyncio.Task | None = None
    try:
        user_prompt = data.get("message", "")
        conversation_id = data.get("conversation_id")
        use_parallel = bool(data.get("parallel", True))
        context_payload = data.get("context") if isinstance(data.get("context"), dict) else None
        integration_payload = None
        if context_payload and isinstance(context_payload.get("integration_settings"), dict):
            integration_payload = context_payload.get("integration_settings")
        integration_preferences = normalize_integration_settings(integration_payload)

        context_prefix = ""
        if context_payload:
            summary = context_payload.get("summary")
            if isinstance(summary, str) and summary.strip():
                context_prefix += f"Conversation summary:\n{summary.strip()}\n\n"
            recent_messages = context_payload.get("recent_messages")
            if isinstance(recent_messages, list):
                formatted_recent = []
                for entry in recent_messages[-8:]:
                    if not isinstance(entry, dict):
                        continue
                    role = entry.get("role", "user")
                    content = entry.get("content", "")
                    if isinstance(content, str) and content.strip():
                        formatted_recent.append(f"{role}: {content.strip()}")
                if formatted_recent:
                    context_prefix += "Recent exchanges:\n" + "\n".join(formatted_recent) + "\n\n"

        rag_guidance = RAG_IMPLEMENTATION_GUIDANCE if _needs_rag_guidance(user_prompt) else ""

        composed_segments: List[str] = []
        if context_prefix:
            composed_segments.append(context_prefix.rstrip())
            composed_segments.append(f"Current user request:\n{user_prompt.strip()}")
        else:
            composed_segments.append(user_prompt.strip())
        if rag_guidance:
            composed_segments.append(rag_guidance)
        composed_prompt = "\n\n".join(segment for segment in composed_segments if segment).strip()

        if not user_prompt:
            await manager.send_json_message({
                "type": "error",
                "message": "Message is required"
            }, client_id)
            return

        # Build the team (reuse the AzureArchitectAgent + streaming responses client)
        architect_agent = azure_clients.get_azure_architect_agent()
        try:
            architect_agent.set_integration_preferences(integration_preferences)
        except AttributeError:
            logger.debug("Architect agent does not expose integration preferences setter.")
        
        # Extract agent configuration from integration preferences
        agent_config = integration_preferences.get("agents", {})
        team = LandingZoneTeam(architect_agent, agent_config=agent_config)

        # Generate a run id up front so we can stream progress immediately
        run_id = tracer.new_run()
        tracer.ensure_run(run_id)

        # Start forwarding trace events to this socket (and to the conversation)
        forwarder = asyncio.create_task(_forward_trace_events(run_id, client_id, conversation_id))

        # Let UI know: run starting with run identifier
        await manager.send_json_message({
            "type": "run_started",
            "conversation_id": conversation_id,
            "run_id": run_id,
        }, client_id)

        if use_parallel:
            final_text, diagram_payload, raw_diagram, iac_bundle, _ = await team.run_parallel_pass_traced(
                composed_prompt, run_id=run_id
            )
        else:
            final_text, diagram_payload, raw_diagram, iac_bundle, _ = await team.run_sequential_traced(
                composed_prompt, run_id=run_id
            )

        if isinstance(diagram_payload, dict):
            services = diagram_payload.get("services") or []
            connections = diagram_payload.get("connections") or []
            groups = diagram_payload.get("groups") or []
            logger.info(
                "LandingZoneTeam diagram summary: services=%d groups=%d connections=%d",
                len(services),
                len(groups),
                len(connections),
            )

        # Send final answer
        await manager.send_json_message({
            "type": "team_final",
            "conversation_id": conversation_id,
            "run_id": run_id,
            "message": final_text,
            "diagram": diagram_payload,
            "diagram_raw": raw_diagram,
            "iac": iac_bundle,
            "timestamp": datetime.utcnow().isoformat()
        }, client_id)

        # Broadcast conversation update
        if conversation_id:
            await manager.broadcast_to_conversation(conversation_id, {
                "type": "conversation_update",
                "conversation_id": conversation_id,
                "user_message": user_prompt,
                "assistant_message": final_text,
                "diagram": diagram_payload,
                "timestamp": datetime.utcnow().isoformat()
            })

        # Signal tracer listeners that the run has completed
        if run_id:
            await tracer.finish(run_id)

        # Mark run complete
        await manager.send_json_message({
            "type": "run_completed",
            "conversation_id": conversation_id,
            "run_id": run_id
        }, client_id)

    except Exception as e:
        logger.error(f"Error in team_stream_chat: {e}")
        await manager.send_json_message({
            "type": "error",
            "message": f"Failed to run agent team: {str(e)}"
        }, client_id)
        if run_id:
            await tracer.finish(run_id)

    finally:
        if forwarder:
            forwarder.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await forwarder

async def handle_subscribe_run(data: dict, client_id: str):
    run_id = data.get("run_id")
    conversation_id = data.get("conversation_id")
    if not run_id:
        await manager.send_json_message({"type": "error", "message": "run_id is required"}, client_id)
        return
    if tracer.is_active(run_id):
        asyncio.create_task(_forward_trace_events(run_id, client_id, conversation_id))
        await manager.send_json_message({"type": "subscribed_run", "run_id": run_id, "mode": "live"}, client_id)
    else:
        await manager.send_json_message({"type": "subscribed_run", "run_id": run_id, "mode": "replay"}, client_id)
        replayed = await _replay_trace_log(run_id, client_id, conversation_id)
        if replayed:
            await manager.send_json_message({"type": "run_completed", "run_id": run_id, "replayed": True}, client_id)
        else:
            await manager.send_json_message({"type": "trace_event_backlog_empty", "run_id": run_id}, client_id)


async def handle_chat_websocket(websocket: WebSocket, client_id: str, azure_clients: AzureClientManager):
    """Handle WebSocket connections for chat."""
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "chat_message":
                await handle_chat_message(data, client_id, azure_clients)
            elif message_type == "join_conversation":
                await handle_join_conversation(data, client_id)
            elif message_type == "stream_chat":
                await handle_stream_chat(data, client_id, azure_clients)
            elif message_type == "analyze_diagram":
                await handle_analyze_diagram(data, client_id, azure_clients)
            elif message_type == "team_stream_chat":
                await handle_team_stream_chat(data, client_id, azure_clients)
            elif message_type == "subscribe_run":
                await handle_subscribe_run(data, client_id)
            else:
                await manager.send_json_message({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                }, client_id)
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        await manager.send_json_message({
            "type": "error",
            "message": f"Server error: {str(e)}"
        }, client_id)


async def handle_chat_message(data: dict, client_id: str, azure_clients: AzureClientManager):
    """Handle regular chat messages."""
    try:
        message = data.get("message", "")
        conversation_id = data.get("conversation_id")
        context_payload = data.get("context")
        history_payload = data.get("conversation_history")
        
        if not message:
            await manager.send_json_message({
                "type": "error",
                "message": "Message is required"
            }, client_id)
            return
        
        # Get the agent
        agent = azure_clients.get_azure_architect_agent()
        
        # Send typing indicator
        await manager.send_json_message({
            "type": "typing",
            "conversation_id": conversation_id
        }, client_id)
        
        context_dict = context_payload if isinstance(context_payload, dict) else None
        history_list = history_payload if isinstance(history_payload, list) else None
        integration_settings = normalize_integration_settings(
            context_dict.get("integration_settings") if isinstance(context_dict, dict) else None
        )
        if hasattr(agent, "set_integration_preferences"):
            agent.set_integration_preferences(integration_settings)

        # Get response from agent
        response = await agent.chat(
            message,
            conversation_history=history_list,
            context=context_dict,
        )
        
        # Send response
        await manager.send_json_message({
            "type": "chat_response",
            "message": response,
            "conversation_id": conversation_id,
            "timestamp": datetime.utcnow().isoformat()
        }, client_id)
        
        # Broadcast to conversation if others are listening
        if conversation_id:
            await manager.broadcast_to_conversation(conversation_id, {
                "type": "conversation_update",
                "conversation_id": conversation_id,
                "user_message": message,
                "assistant_message": response,
                "timestamp": datetime.utcnow().isoformat()
            })
        
    except Exception as e:
        logger.error(f"Error handling chat message: {e}")
        await manager.send_json_message({
            "type": "error",
            "message": f"Failed to process message: {str(e)}"
        }, client_id)


async def handle_stream_chat(data: dict, client_id: str, azure_clients: AzureClientManager):
    """Handle streaming chat messages."""
    try:
        message = data.get("message", "")
        conversation_id = data.get("conversation_id")
        context_payload = data.get("context")
        history_payload = data.get("conversation_history")
        
        if not message:
            await manager.send_json_message({
                "type": "error",
                "message": "Message is required"
            }, client_id)
            return
        
        # Get the agent
        agent = azure_clients.get_azure_architect_agent()
        
        # Send start streaming indicator
        await manager.send_json_message({
            "type": "stream_start",
            "conversation_id": conversation_id
        }, client_id)
        
        context_dict = context_payload if isinstance(context_payload, dict) else None
        history_list = history_payload if isinstance(history_payload, list) else None
        integration_settings = normalize_integration_settings(
            context_dict.get("integration_settings") if isinstance(context_dict, dict) else None
        )
        if hasattr(agent, "set_integration_preferences"):
            agent.set_integration_preferences(integration_settings)

        # Stream response from agent
        full_response = ""
        async for chunk in agent.stream_chat(
            message,
            conversation_history=history_list,
            context=context_dict,
        ):
            full_response += chunk
            await manager.send_json_message({
                "type": "stream_chunk",
                "chunk": chunk,
                "conversation_id": conversation_id
            }, client_id)
        
        # Send end streaming indicator
        await manager.send_json_message({
            "type": "stream_end",
            "conversation_id": conversation_id,
            "full_message": full_response,
            "timestamp": datetime.utcnow().isoformat()
        }, client_id)
        
        # Broadcast to conversation if others are listening
        if conversation_id:
            await manager.broadcast_to_conversation(conversation_id, {
                "type": "conversation_update",
                "conversation_id": conversation_id,
                "user_message": message,
                "assistant_message": full_response,
                "timestamp": datetime.utcnow().isoformat()
            })
        
    except Exception as e:
        logger.error(f"Error handling stream chat: {e}")
        await manager.send_json_message({
            "type": "error",
            "message": f"Failed to stream message: {str(e)}"
        }, client_id)


async def handle_join_conversation(data: dict, client_id: str):
    """Handle joining a conversation for real-time updates."""
    try:
        conversation_id = data.get("conversation_id")
        
        if not conversation_id:
            await manager.send_json_message({
                "type": "error",
                "message": "Conversation ID is required"
            }, client_id)
            return
        
        manager.add_to_conversation(conversation_id, client_id)
        
        await manager.send_json_message({
            "type": "conversation_joined",
            "conversation_id": conversation_id
        }, client_id)
        
    except Exception as e:
        logger.error(f"Error joining conversation: {e}")
        await manager.send_json_message({
            "type": "error",
            "message": f"Failed to join conversation: {str(e)}"
        }, client_id)


async def handle_analyze_diagram(data: dict, client_id: str, azure_clients: AzureClientManager):
    """Handle diagram analysis via WebSocket."""
    try:
        diagram_data = data.get("diagram_data")
        target_region = data.get("target_region", "westeurope")
        conversation_id = data.get("conversation_id")
        
        if not diagram_data:
            await manager.send_json_message({
                "type": "error",
                "message": "Diagram data is required"
            }, client_id)
            return
        
        # Get the agent
        agent = azure_clients.get_azure_architect_agent()
        
        # Send processing indicator
        await manager.send_json_message({
            "type": "analysis_start",
            "conversation_id": conversation_id
        }, client_id)
        # Analyze diagram (synchronous function)
        diagram_json = json.dumps(diagram_data)
        analysis = analyze_diagram(diagram_json, target_region)
        
        # Send analysis result
        await manager.send_json_message({
            "type": "analysis_complete",
            "analysis": analysis,
            "conversation_id": conversation_id,
            "timestamp": datetime.utcnow().isoformat()
        }, client_id)
        
        # Broadcast to conversation if others are listening
        if conversation_id:
            await manager.broadcast_to_conversation(conversation_id, {
                "type": "diagram_analyzed",
                "conversation_id": conversation_id,
                "analysis": analysis,
                "timestamp": datetime.utcnow().isoformat()
            })
        
    except Exception as e:
        logger.error(f"Error analyzing diagram: {e}")
        await manager.send_json_message({
            "type": "error",
            "message": f"Failed to analyze diagram: {str(e)}"
        }, client_id)


async def handle_deployment_websocket(websocket: WebSocket, client_id: str, azure_clients: AzureClientManager):
    """Handle WebSocket connections for deployment monitoring."""
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message_type = data.get("type")
            
            if message_type == "monitor_deployment":
                await handle_monitor_deployment(data, client_id, azure_clients)
            elif message_type == "get_deployment_logs":
                await handle_get_deployment_logs(data, client_id, azure_clients)
            else:
                await manager.send_json_message({
                    "type": "error",
                    "message": f"Unknown message type: {message_type}"
                }, client_id)
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}")
        await manager.send_json_message({
            "type": "error",
            "message": f"Server error: {str(e)}"
        }, client_id)


async def handle_monitor_deployment(data: dict, client_id: str, azure_clients: AzureClientManager):
    """Handle deployment monitoring requests."""
    try:
        deployment_id = data.get("deployment_id")
        
        if not deployment_id:
            await manager.send_json_message({
                "type": "error",
                "message": "Deployment ID is required"
            }, client_id)
            return
        
        # TODO: Implement real deployment monitoring
        # For now, send periodic updates
        await manager.send_json_message({
            "type": "deployment_status",
            "deployment_id": deployment_id,
            "status": "monitoring_started"
        }, client_id)
        
    except Exception as e:
        logger.error(f"Error monitoring deployment: {e}")
        await manager.send_json_message({
            "type": "error",
            "message": f"Failed to monitor deployment: {str(e)}"
        }, client_id)


async def handle_get_deployment_logs(data: dict, client_id: str, azure_clients: AzureClientManager):
    """Handle deployment log requests."""
    try:
        deployment_id = data.get("deployment_id")
        
        if not deployment_id:
            await manager.send_json_message({
                "type": "error",
                "message": "Deployment ID is required"
            }, client_id)
            return
        
        # Load logs from blob storage
        blob_client = azure_clients.get_blob_client()
        container_name = "deployments"
        blob_name = f"{deployment_id}/logs.json"
        
        try:
            blob_data = await blob_client.get_blob_client(
                container=container_name,
                blob=blob_name
            ).download_blob()
            
            logs_data = json.loads(await blob_data.readall())
            
            await manager.send_json_message({
                "type": "deployment_logs",
                "deployment_id": deployment_id,
                "logs": logs_data
            }, client_id)
            
        except Exception:
            # No logs found
            await manager.send_json_message({
                "type": "deployment_logs",
                "deployment_id": deployment_id,
                "logs": []
            }, client_id)
        
    except Exception as e:
        logger.error(f"Error getting deployment logs: {e}")
        await manager.send_json_message({
            "type": "error",
            "message": f"Failed to get deployment logs: {str(e)}"
        }, client_id)
