"""
Azure Architect MAF Agent

This module implements the Microsoft Agent Framework integration for:
- Chat-driven architecture planning
- IaC generation from ReactFlow diagrams
- Azure deployment guidance
- Tool calling for canvas operations
"""

import json
import logging
from typing import Any, Dict, Union
from typing import Any as TypingAny, cast
from app.agents.azure_architect_agent import AzureArchitectAgent



AzureAIAgentClient = cast(TypingAny, globals().get('AzureAIAgentClient') or TypingAny)
OpenAIAssistantsClient = cast(TypingAny, globals().get('OpenAIAssistantsClient') or TypingAny)
OpenAIResponsesClient = cast(TypingAny, globals().get('OpenAIResponsesClient') or TypingAny)

logger = logging.getLogger(__name__)


def _mcp_enabled(agent: AzureArchitectAgent, key: str) -> bool:
    """
    Determine if a given MCP integration is enabled for the agent.

    Falls back to the agent's stored integration preferences when the helper
    isn't available (e.g., older agent instances).
    """
    try:
        return bool(agent.should_use_mcp(key))
    except AttributeError:
        prefs = getattr(agent, "_integration_preferences", {}) or {}
        return bool(prefs.get("mcp", {}).get(key, False))


async def generate_bicep_code(self: AzureArchitectAgent, architecture_description: Union[str, Dict[str, Any]], include_monitoring: bool = True, include_security: bool = True) -> Dict[str, Any]:
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
                resp = await self.chat_agent.run(prompt)
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
                parsed = _extract_json(text) or (json.loads(text) if text.strip().startswith('{') else None)
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

async def generate_terraform_code(self: AzureArchitectAgent, architecture_description: Union[str, Dict[str, Any]], include_monitoring: bool = True, include_security: bool = True, provider: str = "azurerm") -> Dict[str, Any]:
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
        response = await self.chat_agent.run(tf_prompt)
        text = getattr(response, "result", str(response))

        # Extract JSON from response
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                result = json.loads(text[start:end])
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

async def generate_bicep_via_mcp(self: AzureArchitectAgent, diagram: dict, region: str = "westeurope") -> dict:
    """
    Generate Bicep using MCP Bicep schema tools for enhanced accuracy.
    
    Uses the Azure Bicep MCP server to ground the LLM in current schemas,
    reducing hallucinations and improving template correctness.
    
    Returns {'bicep_code': str, 'parameters': dict}
    """
    if not self.chat_agent:
        raise RuntimeError("Agent not initialized")
    if not _mcp_enabled(self, "bicep"):
        raise RuntimeError("Azure Bicep MCP disabled for this project")

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
        if _mcp_enabled(self, "docs"):
            try:
                from app.deps import get_microsoft_docs_mcp_tool
                docs_tool = await get_microsoft_docs_mcp_tool()
                if docs_tool:
                    tools_to_use = [mcp_tool, docs_tool]
            except Exception:
                pass

        # Run with MCP tool available by passing the tool into the run call
        # Note: agent_framework expects tools to be passed either at agent
        # creation or per-run; we provide the streamable MCP tool here.
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

async def validate_bicep_with_mcp(self: AzureArchitectAgent, bicep_code: str) -> dict:
    """
    Validate Bicep code using MCP tools for schema and syntax correctness.
    
    Returns {"valid": boolean, "errors": [str], "warnings": [str]}
    """
    if not self.chat_agent:
        return {"valid": False, "errors": ["Agent not initialized"]}
    if not _mcp_enabled(self, "bicep"):
        raise RuntimeError("Azure Bicep MCP disabled for this project")

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

async def generate_terraform_via_mcp(self: AzureArchitectAgent, diagram: dict, provider: str = "azurerm") -> dict:
    """
    Generate Terraform configuration using MCP tools for schema grounding.
    
    Uses HashiCorp's Terraform MCP server to lookup provider schemas,
    resource types, and examples from the Terraform Registry before
    generating IaC code.
    """
    if not self.chat_agent:
        logger.warning("Agent not initialized, falling back to standard generation")
        return await self.generate_terraform_code({"diagram": diagram, "provider": provider})
    if not _mcp_enabled(self, "terraform"):
        raise RuntimeError("Terraform MCP disabled for this project")

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
        
        resp = await self.chat_agent.run(prompt, tools=tf_mcp)
        text = getattr(resp, "result", str(resp))
        
        # Extract JSON from response
        try:
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end])
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

async def validate_terraform_with_mcp(self: AzureArchitectAgent, terraform_code: str, provider: str = "azurerm") -> dict:
    """
    Validate Terraform configuration using MCP tools for schema and syntax correctness.
    
    Returns {"valid": boolean, "errors": [str], "warnings": [str]}
    """
    if not self.chat_agent:
        return {"valid": False, "errors": ["Agent not initialized"]}
    if not _mcp_enabled(self, "terraform"):
        raise RuntimeError("Terraform MCP disabled for this project")

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
        
        resp = await self.chat_agent.run(prompt, tools=tf_mcp)
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

async def get_terraform_provider_info_via_mcp(self: AzureArchitectAgent, provider: str = "azurerm") -> dict:
    """
    Get provider information and available resources using Terraform MCP.
    
    Useful for understanding what resources are available for a given provider.
    """
    if not self.chat_agent:
        return {"error": "Agent not initialized"}
    if not _mcp_enabled(self, "terraform"):
        raise RuntimeError("Terraform MCP disabled for this project")

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
        
        resp = await self.chat_agent.run(prompt, tools=tf_mcp)
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
