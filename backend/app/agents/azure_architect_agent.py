"""
Azure Architect MAF Agent

This module implements the Microsoft Agent Framework integration for:
- Chat-driven architecture planning
- IaC generation from ReactFlow diagrams
- Azure deployment guidance
- Tool calling for canvas operations
"""

import copy
import json
import logging
from typing import Any, Dict, List, Optional, Union
from app.agents.tools.analyze_diagram import analyze_diagram
from app.agents.tools.plan_deployment import plan_deployment
from app.agents.tools.generate_reactflow_diagram import generate_reactflow_diagram
from app.agents.tools.analyze_image_for_architecture import analyze_image_for_architecture
from app.agents.landing_zone_team import LandingZoneTeam
from typing import Any as TypingAny, cast
from app.agents.diagram_guide_prompts import instructions
try:
    from agent_framework import ChatAgent, ChatMessage, TextContent, UriContent
except Exception:
    # Optional dependencies - allow module to be imported in environments
    # where the agent_framework packages are not installed. Provide
    # lightweight placeholders so code that instantiates message helpers works.
    ChatAgent = None

    class ChatMessage:
        def __init__(self, role=None, contents=None):
            # contents is expected to be a sequence of content objects
            self.role = role
            self.contents = contents or []

        def __repr__(self):
            return f"ChatMessage(role={self.role!r}, contents={self.contents!r})"

    class TextContent:
        def __init__(self, text: str):
            self.text = text

        def __repr__(self):
            return f"TextContent(text={self.text!r})"

    class UriContent:
        def __init__(self, uri: str, media_type: str = None):
            self.uri = uri
            self.media_type = media_type

        def __repr__(self):
            return f"UriContent(uri={self.uri!r}, media_type={self.media_type!r})"

    class AzureAIAgentClient:  # placeholder
        pass

    class OpenAIAssistantsClient:  # placeholder
        pass

    class OpenAIChatClient:  # placeholder
        pass

# To keep static type checkers happy in environments where the real
# agent_framework types differ or aren't installed, normalize the names to
# a permissive Any type for internal use. This avoids brittle type-mismatch
# errors from the analyzer while preserving runtime behavior.
ChatAgent = TypingAny if ChatAgent is None else ChatAgent
ChatMessage = TypingAny if ChatMessage is None else ChatMessage
TextContent = TypingAny if TextContent is None else TextContent
UriContent = TypingAny if UriContent is None else UriContent
AzureAIAgentClient = cast(TypingAny, globals().get('AzureAIAgentClient') or TypingAny)
OpenAIAssistantsClient = cast(TypingAny, globals().get('OpenAIAssistantsClient') or TypingAny)
OpenAIChatClient = cast(TypingAny, globals().get('OpenAIChatClient') or TypingAny)

logger = logging.getLogger(__name__)

# REMOVED: Deterministic generate_bicep_code function
# User requirement: Only use AI for IaC generation, no deterministic fallbacks

class AzureArchitectAgent:
    """Azure Architect MAF Agent for chat-driven architecture planning."""

    def __init__(self, agent_client: TypingAny):
        # Use permissive typing for the injected client to avoid static
        # mismatches with optional dependencies in different environments.
        self.agent_client = agent_client
        self.chat_agent = None
        self.use_vision = hasattr(agent_client, "create_agent") or hasattr(agent_client, "chat")
        self._integration_preferences: Dict[str, Dict[str, bool]] = self._default_integration_preferences()

    async def _resolve_docs_tool(self):
        """Attempt to load the Microsoft Learn documentation MCP tool."""
        if not self.should_use_mcp("docs"):
            logger.debug("[_resolve_docs_tool] docs MCP disabled via integration preferences")
            return None
        try:
            from app.deps import get_microsoft_docs_mcp_tool
            tool = await get_microsoft_docs_mcp_tool()
            if tool:
                logger.info("[_resolve_docs_tool] docs MCP tool loaded successfully")
            return tool
        except Exception as e:
            logger.debug("[_resolve_docs_tool] failed to load docs MCP tool: %s", e)
            return None
        
    async def initialize(self) -> None:
        """Initialize the chat agent with tools."""
        logger.info("Initializing Azure Architect MAF Agent...")
        
        # Define all tools including new vision and diagram generation tools
        tools = [analyze_diagram, plan_deployment, generate_reactflow_diagram]
        
        # Add vision tool only for OpenAI Responses client
        if self.use_vision:
            tools.append(analyze_image_for_architecture)
        

        # Create agent with appropriate client
        # Create agent using whichever client API is available. Use getattr
        # to avoid static type errors when optional libs are missing.
        try:
            create_fn = getattr(self.agent_client, "create_agent", None)
            if callable(create_fn):
                # Some clients accept a name parameter; be permissive.
                try:
                    self.chat_agent = create_fn(name="AzureArchitectAgent", instructions=instructions, tools=tools)
                except TypeError:
                    # Fallback to calling without name
                    self.chat_agent = create_fn(instructions=instructions, tools=tools)
            else:
                # If the client doesn't provide create_agent, assume it can act
                # as a chat client directly or will be wrapped elsewhere.
                self.chat_agent = getattr(self.agent_client, "chat", None) or getattr(self.agent_client, "run", None)
        except Exception:
            self.chat_agent = None
        
        logger.info(f"Azure Architect MAF Agent initialized successfully (Vision: {self.use_vision})")

    def _default_integration_preferences(self) -> Dict[str, Dict[str, bool]]:
        return {
            "mcp": {
                "bicep": False,
                "terraform": False,
                "docs": False,
            }
        }

    def set_integration_preferences(self, preferences: Optional[Dict[str, Any]]) -> None:
        merged = self._default_integration_preferences()
        if isinstance(preferences, dict):
            mcp_settings = preferences.get("mcp")
            if isinstance(mcp_settings, dict):
                merged["mcp"]["bicep"] = bool(mcp_settings.get("bicep", merged["mcp"]["bicep"]))
                merged["mcp"]["terraform"] = bool(mcp_settings.get("terraform", merged["mcp"]["terraform"]))
                merged["mcp"]["docs"] = bool(mcp_settings.get("docs", merged["mcp"]["docs"]))
        self._integration_preferences = merged

    def get_integration_preferences(self) -> Dict[str, Dict[str, bool]]:
        return copy.deepcopy(self._integration_preferences)

    def should_use_mcp(self, key: str) -> bool:
        return bool(self._integration_preferences.get("mcp", {}).get(key, False))

        
    async def chat_team(self, message: str, parallel_pass: bool = False) -> str:
        agent_config = self._integration_preferences.get("agents", {})
        team = LandingZoneTeam(self, agent_config=agent_config)
        if parallel_pass:
            return await team.run_with_parallel_pass(message)
        return await team.run_sequential(message)
        
    async def chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Send a message to the agent and get a response."""
        if not self.chat_agent:
            raise RuntimeError("Agent not initialized")
        
        try:
            composed_prompt = self._compose_prompt(message, conversation_history, context)
            logger.info("[agent-chat] prompt characters=%s", len(composed_prompt))
            response = await self.chat_agent.run(composed_prompt)
            result = getattr(response, "result", None)
            if isinstance(result, str) and result.strip():
                return result
            text = getattr(response, "text", None)
            if isinstance(text, str) and text.strip():
                return text
            return str(response)
            
        except Exception as e:
            logger.error(f"Error in agent chat: {e}")
            return f"I apologize, but I encountered an error: {str(e)}"
    
    async def stream_chat(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Stream chat response from the agent."""
        if not self.chat_agent:
            raise RuntimeError("Agent not initialized")
        
        try:
            composed_prompt = self._compose_prompt(message, conversation_history, context)
            async for chunk in self.chat_agent.run_stream(composed_prompt):
                # Extract text from AgentRunResponseUpdate
                text = None
                if hasattr(chunk, 'text') and chunk.text:
                    text = str(chunk.text)
                elif hasattr(chunk, 'data'):
                    data = chunk.data
                    if isinstance(data, str):
                        text = data
                    elif hasattr(data, 'content') and data.content:
                        text = str(data.content)
                
                if text:
                    print(f"[AGENT-STREAM] ✓ Token: {repr(text[:50])}")
                    yield text
                    
        except Exception as e:
            print(f"[AGENT-STREAM] ERROR: {e}")
            import traceback
            traceback.print_exc()
            logger.error(f"Error in agent stream chat: {e}")
            yield f"I apologize, but I encountered an error: {str(e)}"
    
    def _compose_prompt(
        self,
        message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Compose a prompt for the agent that includes structured context."""
        prefix_parts: List[str] = []

        if context:
            summary = context.get("summary")
            if isinstance(summary, str) and summary.strip():
                prefix_parts.append(f"Conversation summary:\n{summary.strip()}")

            recent = context.get("recent_messages")
            if isinstance(recent, list):
                formatted_recent: List[str] = []
                for entry in recent[-8:]:
                    if not isinstance(entry, dict):
                        continue
                    role = entry.get("role", "user")
                    content = entry.get("content", "")
                    if isinstance(content, str) and content.strip():
                        formatted_recent.append(f"{role}: {content.strip()}")
                if formatted_recent:
                    prefix_parts.append("Recent exchanges:\n" + "\n".join(formatted_recent))

        if conversation_history:
            formatted_history: List[str] = []
            for msg in conversation_history[-10:]:
                if not isinstance(msg, dict):
                    continue
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if isinstance(content, str) and content.strip():
                    formatted_history.append(f"{role}: {content.strip()}")
            if formatted_history:
                prefix_parts.append("Conversation history:\n" + "\n".join(formatted_history))

        user_request = message.strip()
        if prefix_parts:
            prefix_parts.append(f"Current user request:\n{user_request}")
            return "\n\n".join(prefix_parts)
        return user_request
            
    async def analyze_image_with_chat(self, image_url: str, prompt: str = "Analyze this architecture diagram and create a ReactFlow diagram for it") -> str:
        """Analyze an image using vision capabilities (OpenAI only)."""
        if not self.use_vision or not self.chat_agent:
            return "Image analysis not available with current configuration"
        
        try:
            # If the ChatMessage/TextContent/UriContent helpers are available
            # and callable, use them; otherwise fall back to a simple text
            # prompt that includes the image URL.
            if callable(ChatMessage) and callable(TextContent) and callable(UriContent):
                message = ChatMessage(
                    role="user",
                    contents=[
                        TextContent(text=prompt),
                        UriContent(uri=image_url, media_type="image/jpeg")
                    ]
                )
                resp = await self.chat_agent.run(message)
                return getattr(resp, "result", str(resp))
            else:
                # Fallback: append image URL to the prompt
                text_prompt = f"{prompt}\nImage: {image_url}"
                resp = await self.chat_agent.run(text_prompt)
                return getattr(resp, "result", str(resp))
        except Exception as e:
            logger.error(f"Error in image analysis: {e}")
            return f"I apologize, but I encountered an error analyzing the image: {str(e)}"

    async def generate_bicep_code(self, architecture_description: Union[str, Dict[str, Any]], include_monitoring: bool = True, include_security: bool = True) -> Dict[str, Any]:
        """Compatibility wrapper used by the /api/iac endpoint.

        The endpoint historically called `agent.generate_bicep_code(...)`. The
        AzureArchitectAgent exposes the diagram-generation tool as a standalone
        function; here we provide an async wrapper that accepts either a
        pre-parsed diagram (dict) or a prompt string that contains a JSON
        'Diagram Data' block. It returns a dict with a `bicep_code` entry so
        the existing /api/iac flow continues to work.
        """
        try:
            # Normalize architecture_description into diagram dict
            # Ensure service_configs is always defined to avoid unbound variable
            service_configs = {}
            if isinstance(architecture_description, dict):
                # Support two shapes: either the diagram dict directly, or a
                # wrapper { "diagram": {...}, "service_configs": {...} }
                if "diagram" in architecture_description:
                    diagram = architecture_description.get("diagram") or {"nodes": [], "edges": []}
                    service_configs = architecture_description.get("service_configs") or {}
                else:
                    diagram = architecture_description
                    service_configs = {}
            else:
                raw_text = str(architecture_description)
                diagram = None
                marker = "Diagram Data:"
                if marker in raw_text:
                    idx = raw_text.index(marker) + len(marker)
                    rest = raw_text[idx:]
                    brace_start = rest.find('{')
                    if brace_start != -1:
                        depth = 0
                        end = -1
                        for i, ch in enumerate(rest[brace_start:]):
                            if ch == '{': depth += 1
                            elif ch == '}':
                                depth -= 1
                                if depth == 0:
                                    end = brace_start + i + 1
                                    break
                        if end != -1:
                            json_blob = rest[brace_start:end]
                            try:
                                diagram = json.loads(json_blob)
                            except Exception:
                                diagram = None
                if diagram is None:
                    try:
                        diagram = json.loads(raw_text)
                    except Exception:
                        diagram = {"nodes": [], "edges": []}

            # Decide if we should invoke the model. With MAF the user expects AI involvement.
            force_model = False
            if isinstance(architecture_description, dict):
                force_model = bool(architecture_description.get("_force_model", False))

            # If service_configs are provided, merge them into each node's data
            try:
                nodes = diagram.get("nodes", []) if isinstance(diagram, dict) else []
                if isinstance(service_configs, dict) and isinstance(nodes, list):
                    for n in nodes:
                        nid = n.get("id") or (n.get("data") or {}).get("id")
                        if not nid:
                            continue
                        sc = service_configs.get(nid)
                        if sc and isinstance(n.get("data"), dict):
                            # Merge shallowly; do not overwrite existing nested maps unless present
                            n_data = n.get("data") or {}
                            for k, v in (sc.items() if isinstance(sc, dict) else []):
                                if v is not None:
                                    n_data.setdefault(k, v)
                            n["data"] = n_data
            except Exception:
                # Non-fatal; proceed without enriched data
                pass

            # Always attempt model first if chat_agent exists (unless explicitly disabled via _force_model=False).
            if self.chat_agent:
                try:
                    instruction = (
                        "You are an Azure Cloud Infrastructure as Code generator. Given the diagram JSON under 'diagram', "
                        "author a subscription-scoped Bicep template that can stand up a production-grade landing zone. "
                        "Requirements:\n"
                        "- Start with `targetScope = 'subscription'`.\n"
                        "- Declare core parameters: location, environment (allowed dev/tst/prd), namePrefix (min/max length), optional tags object, and any network CIDRs needed for vnets/subnets.\n"
                        "- Create a resource group per top-level workload grouping (e.g., networking, management, logging, shared integration) and deploy resources inside using `module` blocks or inline `resource` definitions scoped to those groups.\n"
                        "- Map every service from the diagram to a concrete Azure resource type (Microsoft.Network/*, Microsoft.Storage/*, etc.) with realistic API versions, SKU settings, and key properties (identity, diagnostics, access policies). Do not omit services—extend the template when the diagram lacks an obvious Azure equivalent.\n"
                        "- Wire dependencies properly (e.g., subnet IDs, private endpoints, diagnostic settings to Log Analytics) and include optional monitoring/security resources when include_monitoring/include_security flags are true.\n"
                        "- Provide useful outputs for core artifacts (vnetId, key vault IDs, workspace keys, etc.).\n"
                        "- Return ONLY a JSON object with keys `bicep_code` (string containing the full template) and `parameters` (object describing parameter defaults/metadata). No markdown, no commentary."
                    )
                    payload = {
                        "diagram": {"nodes": diagram.get("nodes", []), "edges": diagram.get("edges", [])},
                        "requirements": {
                            "target_format": "bicep",
                            "include_monitoring": include_monitoring,
                            "include_security": include_security,
                        },
                    }
                    prompt = f"{instruction}\n\nDiagram Data: {json.dumps(payload, separators=(',',':'))}"
                    run_kwargs: Dict[str, Any] = {}
                    docs_tool = await self._resolve_docs_tool()
                    if docs_tool:
                        run_kwargs["tools"] = docs_tool
                    resp = await self.chat_agent.run(prompt, **run_kwargs)
                    text = getattr(resp, "result", str(resp))
                    # Attempt robust JSON extraction
                    def _extract_json(txt: str):
                        start = txt.find('{')
                        if start == -1: return None
                        depth = 0
                        for i, ch in enumerate(txt[start:]):
                            if ch == '{': depth += 1
                            elif ch == '}':
                                depth -= 1
                                if depth == 0:
                                    end = start + i + 1
                                    try:
                                        return json.loads(txt[start:end])
                                    except Exception:
                                        return None
                        return None
                    parsed = _extract_json(text)
                    if not parsed and text.strip().startswith('{'):
                        try:
                            # Try parsing with strict=False to handle escape sequences
                            parsed = json.loads(text, strict=False)
                        except Exception:
                            pass
                    if parsed and isinstance(parsed, dict) and parsed.get("bicep_code"):
                        return {"bicep_code": parsed.get("bicep_code", ""), "parameters": parsed.get("parameters", {})}
                    else:
                        logger.warning("MAF agent returned no parsable bicep_code; falling back to deterministic generator")
                except Exception as e:
                    logger.exception("MAF model call failed, falling back to deterministic generator: %s", e)

            # No deterministic fallback - AI only!
            logger.error("AI generation failed and no deterministic fallback available")
            return {"bicep_code": "", "parameters": {"error": "AI generation failed - no deterministic fallback available"}}
        except Exception as e:
            logger.error(f"Error in generate_bicep_code wrapper: {e}")
            return {"bicep_code": "", "parameters": {}, "error": str(e)}

    async def generate_terraform_code(self, architecture_description: Union[str, Dict[str, Any]], include_monitoring: bool = True, include_security: bool = True, provider: str = "azurerm") -> Dict[str, Any]:
        """Generate Terraform HCL using AI-only approach."""
        if not self.chat_agent:
            raise RuntimeError("Agent not initialized")

        try:
            # Prepare the prompt based on input type
            if isinstance(architecture_description, dict):
                context = json.dumps(architecture_description, indent=2)
            else:
                context = str(architecture_description)

            monitoring_context = " Include monitoring and alerting resources." if include_monitoring else ""
            security_context = " Include security best practices and configurations." if include_security else ""

            tf_prompt = f"""
            Generate comprehensive Terraform HCL configuration for this Azure architecture:

            {context}

            Requirements:
            - Use {provider} provider
            - Include all necessary resource configurations
            - Add appropriate variables and outputs
            - Use consistent naming conventions
            - Include resource dependencies{monitoring_context}{security_context}

            Return ONLY valid JSON in this format:
            {{
                "terraform_code": "complete HCL configuration as string",
                "parameters": {{
                    "provider": "{provider}",
                    "region": "westeurope"
                }}
            }}
            """

            logger.debug("Generating Terraform via MAF agent")
            run_kwargs: Dict[str, Any] = {}
            # Only attempt docs tool if enabled via integration preferences
            if self.should_use_mcp("docs"):
                docs_tool = await self._resolve_docs_tool()
                if docs_tool:
                    run_kwargs["tools"] = docs_tool
            resp = await self.chat_agent.run(tf_prompt, **run_kwargs)
            text = getattr(resp, "result", str(resp))

            # Extract JSON from response
            try:
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = text[start:end]
                    # Remove control characters that can break JSON parsing
                    import re
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
                    result = json.loads(json_str, strict=False)
                    # Ensure expected structure
                    return {
                        "terraform_code": result.get("terraform_code", ""),
                        "parameters": result.get("parameters", {"provider": provider})
                    }
            except Exception as parse_error:
                logger.warning(f"Failed to parse Terraform JSON response: {parse_error}")
                # Return text as-is if JSON parsing fails
                return {
                    "terraform_code": text,
                    "parameters": {"provider": provider}
                }

        except Exception as e:
            logger.error(f"Error in generate_terraform_code: {e}")
            return {"terraform_code": "", "parameters": {"provider": provider}, "error": str(e)}

    async def generate_bicep_via_mcp(self, diagram: dict, region: str = "westeurope") -> dict:
        """
        Generate Bicep using MCP Bicep schema tools for enhanced accuracy.
        
        Uses the Azure Bicep MCP server to ground the LLM in current schemas,
        reducing hallucinations and improving template correctness.
        
        Returns {'bicep_code': str, 'parameters': dict}
        """
        if not self.chat_agent:
            raise RuntimeError("Agent not initialized")

        try:
            # Import and get MCP tool
            from app.deps import get_mcp_bicep_tool
            mcp_tool = await get_mcp_bicep_tool()
            
            if mcp_tool is None:
                logger.warning("MCP Bicep tool not available, falling back to standard generation")
                return await self.generate_bicep_code({"diagram": diagram})

            # Build instruction that emphasizes MCP usage
            instruction = (
                "You are an Azure IaC generator with access to Azure Bicep MCP tools. "
                "Use the MCP tools to confirm resource types, apiVersions, required properties, and SKU options "
                "for every element in the diagram. Emit a subscription-scoped landing-zone template that mirrors the diagram hierarchy:\n"
                "- Declare parameters (location, environment, namePrefix, tags, address prefixes, secret placeholders) with @description metadata.\n"
                "- Provision resource groups/modules for networking, management, logging, runtime, storage, integration, etc., and ensure each service is represented with realistic configuration (identities, diagnostic settings, access policies, SKU tiers).\n"
                "- Add monitoring/security integrations when appropriate (Log Analytics workspace, Policy assignments, Defender, Key Vault).\n"
                "- Include outputs for critical resources.\n"
                "Return ONLY JSON with keys 'bicep_code' (string) and 'parameters' (object). No markdown, no commentary."
            )
            
            payload = {
                "diagram": {"nodes": diagram.get("nodes", []), "edges": diagram.get("edges", [])},
                "requirements": {
                    "target_format": "bicep",
                    "include_monitoring": True,
                    "include_security": True,
                    "region": region
                },
            }
            
            prompt = f"{instruction}\n\nDiagram Data: {json.dumps(payload, separators=(',',':'))}"

            tools_to_use = mcp_tool
            try:
                from app.deps import get_microsoft_docs_mcp_tool
                docs_tool = await get_microsoft_docs_mcp_tool()
                if docs_tool:
                    tools_to_use = [mcp_tool, docs_tool]
            except Exception:
                pass

            # Run with MCP tool available by passing the tool into the run call
            # Note: agent_framework expects tools to be passed either at agent
            # creation or per-run; we provide the streamable MCP tool here (and docs MCP when available).
            resp = await self.chat_agent.run(prompt, tools=tools_to_use)
            text = getattr(resp, "result", str(resp))

            # Robust JSON extraction (same as standard method)
            def _extract_json(txt: str):
                start = txt.find('{')
                if start == -1: 
                    return None
                depth = 0
                for i, ch in enumerate(txt[start:]):
                    if ch == '{': 
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            end = start + i + 1
                            try: 
                                return json.loads(txt[start:end])
                            except Exception: 
                                return None
                return None

            parsed = _extract_json(text) or (json.loads(text) if text.strip().startswith('{') else None)
            if not parsed or "bicep_code" not in parsed:
                raise ValueError("MCP-enhanced Bicep generation failed - no valid bicep_code returned")
                
            return {
                "bicep_code": parsed.get("bicep_code", ""),
                "parameters": parsed.get("parameters", {})
            }
            
        except Exception as e:
            logger.exception(f"MCP Bicep generation failed: {e}")
            # Fall back to standard generation if MCP fails
            logger.info("Falling back to standard Bicep generation")
            return await self.generate_bicep_code({"diagram": diagram})

    async def validate_bicep_with_mcp(self, bicep_code: str) -> dict:
        """
        Validate Bicep code using MCP tools for schema and syntax correctness.
        
        Returns {"valid": boolean, "errors": [str], "warnings": [str]}
        """
        if not self.chat_agent:
            return {"valid": False, "errors": ["Agent not initialized"]}

        try:
            from app.deps import get_mcp_bicep_tool
            mcp_tool = await get_mcp_bicep_tool()
            
            if mcp_tool is None:
                return {"valid": False, "errors": ["MCP Bicep tool not available"]}

            prompt = (
                "Validate this Bicep template for syntax and schema correctness using "
                "Azure Bicep MCP tools. Check resource types, properties, and API versions. "
                "Return ONLY JSON: {\"valid\": boolean, \"errors\": [\"...\"], \"warnings\": [\"...\"]}\n\n"
                f"```bicep\n{bicep_code}\n```"
            )
            
            resp = await self.chat_agent.run(prompt)
            text = getattr(resp, "result", str(resp))
            
            # Extract JSON from response
            try:
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    validation_result = json.loads(text[start:end])
                    # Ensure expected structure
                    return {
                        "valid": validation_result.get("valid", False),
                        "errors": validation_result.get("errors", []),
                        "warnings": validation_result.get("warnings", [])
                    }
            except Exception:
                pass
                
            return {"valid": False, "errors": ["Unable to parse MCP validation response"]}
            
        except Exception as e:
            logger.exception(f"MCP Bicep validation failed: {e}")
            return {"valid": False, "errors": [f"Validation error: {str(e)}"]}

    async def generate_terraform_via_mcp(self, diagram: dict, provider: str = "azurerm") -> dict:
        """
        Generate Terraform configuration using MCP tools for schema grounding.
        
        Uses HashiCorp's Terraform MCP server to lookup provider schemas,
        resource types, and examples from the Terraform Registry before
        generating IaC code.
        """
        if not self.chat_agent:
            logger.warning("Agent not initialized, falling back to standard generation")
            return await self.generate_terraform_code({"diagram": diagram, "provider": provider})

        try:
            from app.deps import get_mcp_terraform_tool
            tf_mcp = await get_mcp_terraform_tool()
            
            if tf_mcp is None:
                logger.info("Terraform MCP tool not available, falling back to standard generation")
                return await self.generate_terraform_code({"diagram": diagram, "provider": provider})

            prompt = (
                "Generate Terraform modules for this Azure architecture diagram. "
                "Use the Terraform MCP tools to lookup providers, resources, arguments, and examples "
                "from the Terraform Registry before emitting code. Ensure all resource types and "
                "arguments are valid for the specified provider version. "
                "Return ONLY JSON: {'terraform_code': string, 'variables': object, 'outputs': object}.\n\n"
                f"Diagram: {json.dumps(diagram, separators=(',',':'))}\n"
                f"Provider: {provider}"
            )
            
            docs_tool = await self._resolve_docs_tool()
            tools_to_use = tf_mcp if not docs_tool else [tf_mcp, docs_tool]
            resp = await self.chat_agent.run(prompt, tools=tools_to_use)
            text = getattr(resp, "result", str(resp))
            
            # Extract JSON from response
            try:
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = text[start:end]
                    # Remove control characters that can break JSON parsing
                    import re
                    json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)
                    parsed = json.loads(json_str, strict=False)
                    return {
                        "terraform_code": parsed.get("terraform_code", ""),
                        "variables": parsed.get("variables", {}),
                        "outputs": parsed.get("outputs", {}),
                        "provider": provider
                    }
            except Exception as parse_err:
                logger.warning(f"Failed to parse MCP Terraform response: {parse_err}")
                
            # If JSON parsing fails, extract text content
            logger.info("JSON parsing failed, attempting text extraction")
            return {
                "terraform_code": text,
                "variables": {},
                "outputs": {},
                "provider": provider
            }
            
        except Exception as e:
            logger.exception(f"MCP Terraform generation failed: {e}")
            # Fall back to standard generation if MCP fails
            logger.info("Falling back to standard Terraform generation")
            return await self.generate_terraform_code({"diagram": diagram, "provider": provider})

    async def validate_terraform_with_mcp(self, terraform_code: str, provider: str = "azurerm") -> dict:
        """
        Validate Terraform configuration using MCP tools for schema and syntax correctness.
        
        Returns {"valid": boolean, "errors": [str], "warnings": [str]}
        """
        if not self.chat_agent:
            return {"valid": False, "errors": ["Agent not initialized"]}

        try:
            from app.deps import get_mcp_terraform_tool
            tf_mcp = await get_mcp_terraform_tool()
            
            if tf_mcp is None:
                return {"valid": False, "errors": ["Terraform MCP tool not available"]}

            prompt = (
                "Validate this Terraform configuration for syntax and provider schema correctness using "
                "Terraform MCP tools. Check resource types, arguments, and provider requirements. "
                f"Provider: {provider}. "
                "Return ONLY JSON: {\"valid\": boolean, \"errors\": [\"...\"], \"warnings\": [\"...\"]}\n\n"
                f"```hcl\n{terraform_code}\n```"
            )
            
            tools_to_use = [tf_mcp]
            if self.should_use_mcp("docs"):
                docs_tool = await self._resolve_docs_tool()
                if docs_tool:
                    tools_to_use.append(docs_tool)
            resp = await self.chat_agent.run(prompt, tools=tools_to_use)
            text = getattr(resp, "result", str(resp))
            
            # Extract JSON from response
            try:
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    validation_result = json.loads(text[start:end])
                    # Ensure expected structure
                    return {
                        "valid": validation_result.get("valid", False),
                        "errors": validation_result.get("errors", []),
                        "warnings": validation_result.get("warnings", [])
                    }
            except Exception:
                pass
                
            return {"valid": False, "errors": ["Unable to parse MCP validation response"]}
            
        except Exception as e:
            logger.exception(f"MCP Terraform validation failed: {e}")
            return {"valid": False, "errors": [f"Validation error: {str(e)}"]}

    async def get_terraform_provider_info_via_mcp(self, provider: str = "azurerm") -> dict:
        """
        Get provider information and available resources using Terraform MCP.
        
        Useful for understanding what resources are available for a given provider.
        """
        if not self.chat_agent:
            return {"error": "Agent not initialized"}

        try:
            from app.deps import get_mcp_terraform_tool
            tf_mcp = await get_mcp_terraform_tool()
            
            if tf_mcp is None:
                return {"error": "Terraform MCP tool not available"}

            prompt = (
                f"Get provider information for '{provider}' including available resource types, "
                "data sources, and recent version information using Terraform MCP tools. "
                "Return ONLY JSON: {\"provider\": string, \"version\": string, \"resources\": [string], \"data_sources\": [string]}"
            )
            
            tools_to_use = [tf_mcp]
            if self.should_use_mcp("docs"):
                docs_tool = await self._resolve_docs_tool()
                if docs_tool:
                    tools_to_use.append(docs_tool)
            resp = await self.chat_agent.run(prompt, tools=tools_to_use)
            text = getattr(resp, "result", str(resp))
            
            # Extract JSON from response
            try:
                start = text.find('{')
                end = text.rfind('}') + 1
                if start >= 0 and end > start:
                    return json.loads(text[start:end])
            except Exception:
                pass
                
            return {"error": "Unable to parse provider info response"}
            
        except Exception as e:
            logger.exception(f"MCP provider info lookup failed: {e}")
            return {"error": f"Provider info error: {str(e)}"}
