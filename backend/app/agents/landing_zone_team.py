# app/agents/teams/landing_zone_team.py
import asyncio
import inspect
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from agent_framework import ChatMessage, Role, SequentialBuilder, ConcurrentBuilder, WorkflowOutputEvent
from app.agents.diagram_guide_prompts import STRUCTURED_DIAGRAM_GUIDANCE, security_instructions, writer_instructions, final_editor_instructions

from app.obs.tracing import tracer, TraceEvent

logger = logging.getLogger(__name__)


def _redact_guidance(text: str | None) -> str | None:
    """Redact or truncate any embedded large guidance blocks before returning or emitting to clients.

    - If the authoritative `STRUCTURED_DIAGRAM_GUIDANCE` block appears, replace it with a short placeholder.
    - If the text is extremely long, truncate with a clear marker.
    """
    if text is None:
        return None
    s = str(text)
    try:
        if STRUCTURED_DIAGRAM_GUIDANCE and STRUCTURED_DIAGRAM_GUIDANCE in s:
            s = s.replace(STRUCTURED_DIAGRAM_GUIDANCE, "[REDACTED STRUCTURED_DIAGRAM_GUIDANCE]")
    except Exception:
        # Be conservative: on any issue, fall back to returning a truncated string
        pass
    # Generic truncation guard for extremely long assistant outputs
    max_len = 25000
    if len(s) > max_len:
        return s[:max_len] + "\n\n[... output truncated ...]"
    return s


def _shorten_for_tracing(text: str | None, max_len: int = 1200) -> str | None:
    if text is None:
        return None
    s = str(text)
    if len(s) <= max_len:
        return s
    return s[:max_len] + "...[TRUNCATED]"

WAF_PILLARS = ["Security", "Reliability", "Cost Optimization", "Operational Excellence", "Performance Efficiency"]

DIAGRAM_SECTION_REGEX = re.compile(
    r"Diagram JSON\s*```json\s*(\{.*?\})\s*```",
    re.IGNORECASE | re.DOTALL,
)


def _agent(chat_client, name: str, instructions: str):
    return chat_client.create_agent(name=name, instructions=instructions)

def _security_instr():
    return security_instructions

def _naming_instr():
    return (
        "You are an Azure naming enforcer. Rewrite resource names to official Azure naming conventions used by this org. "
        "Add tags { env, owner, costCenter, dataClassification }. Keep the technical design intact. "
        "Do not drop any services or groups configured by previous reviewers; instead, ensure naming/tagging consistency across the full set.\n"
        "Output only the updated architecture text and the naming table. Preserve and adjust the `Diagram JSON` section."
    )

def _reliability_instr():
    return (
        "You are an Azure reliability reviewer. Enforce multi-AZ/region strategy where appropriate, "
        "backup/restore, DR/RTO/RPO notes, autoscale and health probes. "
        "If redundancy requires additional services (e.g., paired regions, geo-redundant storage), add them while keeping all previously defined components.\n"
        "Output: improved architecture + a Reliability checklist with decisions. Update the `Diagram JSON` section to reflect any topology changes."
    )

def _cost_perf_instr():
    return (
        "You are an Azure cost/perf optimizer. Right-size SKUs, reserve/spot where relevant, "
        "auto-pause for dev/test, lifecycle policies for storage, caching layers, query patterns. "
        "Retain the full architecture footprint—apply cost guidance without deleting tiers; add shared services (e.g., caching, autoscale rules) only when they complement the design.\n\n"
        "MIGRATION COST ANALYSIS:\n"
        "If the architecture includes AWS or GCP services (detected by service IDs like 'aws:*' or 'gcp:*'), perform a detailed cost comparison:\n"
        "1. Identify each source cloud service and its Azure equivalent\n"
        "2. Estimate monthly costs for both platforms based on:\n"
        "   - Compute: vCPU count, memory, runtime hours\n"
        "   - Storage: capacity (GB/TB), I/O operations, redundancy level\n"
        "   - Database: DTU/vCore tier, storage, backup retention\n"
        "   - Networking: data transfer (GB), bandwidth\n"
        "3. Use realistic pricing (as of late 2024/early 2025):\n"
        "   - AWS: EC2 t3.medium ~$30/mo, RDS db.t3.medium ~$50/mo, S3 Standard $0.023/GB\n"
        "   - Azure: B2s VM ~$30/mo, SQL DB S3 ~$75/mo, Blob Storage GRS $0.024/GB\n"
        "   - GCP: e2-medium ~$25/mo, Cloud SQL db-n1-standard-1 ~$45/mo, Cloud Storage $0.020/GB\n"
        "4. Generate a cost_summary object with:\n"
        "   - currency: 'USD'\n"
        "   - aws_monthly_total or gcp_monthly_total: sum of all source services\n"
        "   - azure_monthly_total: sum of all Azure equivalents\n"
        "   - delta: azure_monthly_total - source_monthly_total\n"
        "   - savings: source_monthly_total - azure_monthly_total\n"
        "   - savings_percent: (savings / source_monthly_total) * 100\n"
        "   - verdict: concise statement like 'Migration to Azure saves 15% monthly' or 'Azure costs 8% more but offers better performance'\n"
        "   - summary_markdown: 2-3 sentence analysis explaining key cost drivers and recommendations\n"
        "   - per_service: array of service-level comparisons with fields:\n"
        "     * node_id: original service node ID\n"
        "     * aws_service / gcp_service: source service name\n"
        "     * azure_service: equivalent Azure service name\n"
        "     * aws_monthly / gcp_monthly: estimated monthly cost on source platform\n"
        "     * azure_monthly: estimated monthly cost on Azure\n"
        "     * delta: azure_monthly - source_monthly\n"
        "     * savings_percent: ((source_monthly - azure_monthly) / source_monthly) * 100\n"
        "     * assumptions: brief note like 'based on 730h/mo runtime, 100GB storage'\n\n"
        "Output: improved architecture + 5 concrete cost levers. If migration detected, include detailed cost_summary in parameters. "
        "Maintain the `Diagram JSON` section and adjust resource SKUs there when needed."
    )

def _compliance_instr():
    return (
        "You are a fintech compliance reviewer. Call out items related to audit logging, immutable logs, "
        "separation of duties, data residency, encryption, and key management. "
        "Preserve every existing workload; add required governance components (e.g., Policy, Blueprints, Monitor, Purview) rather than replacing services, and record them in the `Diagram JSON` with proper hierarchy.\n"
        "Output: improved architecture + short compliance checklist. Ensure any compliance-driven changes are reflected inside the `Diagram JSON` output."
    )

def _final_editor_instr():
    return final_editor_instructions

def _writer_instr():
    return writer_instructions

def _identity_instr():
    return (
        "You are an Identity & Governance reviewer. Review the draft for Entra ID design, role assignments, \n"
        "managed identities, least-privilege RBAC, PIM hints, subscription/management-group boundaries, \n"
        "and suggest Azure Policy initiatives or guardrails.\n"
        "IMPORTANT: Preserve ALL existing services from the architect's design. Add identity and governance \n"
        "components (Azure AD resources, RBAC assignments, Policies, Management Groups) to strengthen security \n"
        "and compliance without removing existing workloads.\n"
        "Output a concise RBAC plan, policy suggestions, and any required changes to the Diagram JSON with \n"
        "proper hierarchy for all governance resources."
    )


def _networking_instr():
    return (
        "You are a Networking reviewer. Validate the network topology for hub-spoke or other recommended patterns, \n"
        "private endpoints, NSG/ASG placement, peering, routing, and hybrid connectivity.\n"
        "IMPORTANT: Preserve ALL existing services from the architect's design. Add networking-specific components \n"
        "(NSGs, route tables, private DNS zones, etc.) to enhance the architecture, don't replace it.\n"
        "Provide concrete changes to the Diagram JSON and a short justification for each network decision. \n"
        "Ensure every new networking component is added to the `Diagram JSON` with correct parentage and connections."
    )


def _observability_instr():
    return (
        "You are an Observability reviewer. Ensure the design includes monitoring, logging, diagnostic settings, \n"
        "Log Analytics/metrics placement, alert rules, and SLOs.\n"
        "IMPORTANT: Preserve ALL existing services from the architect's design. Add monitoring and logging \n"
        "resources (Application Insights, Log Analytics Workspace, Diagnostic Settings, Alerts, Dashboards) \n"
        "to complement the architecture, don't replace existing components.\n"
        "Return a monitoring checklist, recommended telemetry resources, and any Diagram JSON additions needed \n"
        "to represent monitoring/logging components with proper hierarchy and connections."
    )


def _data_storage_instr():
    return (
        "You are a Data & Storage reviewer. Evaluate data flows, storage choices, retention, backups, encryption, \n"
        "and data residency. Recommend storage account configurations, database choices, lifecycle policies, \n"
        "and backup/restore strategies.\n"
        "IMPORTANT: Preserve ALL existing services and databases from the architect's design. Add data management \n"
        "components (backup vaults, storage policies, data lifecycle rules, encryption keys) to enhance data \n"
        "protection and compliance, don't replace existing storage/database resources.\n"
        "Provide any Diagram JSON updates needed to represent data storage components with complete hierarchy."
    )

class LandingZoneTeam:
    def __init__(self, agent_source, agent_config: dict | None = None):
        """
        Initialize the landing zone team.

        `agent_source` can be either the high-level AzureArchitectAgent or the raw chat client.
        When the full agent is supplied we retain a reference so we can invoke its IaC generators.
        
        `agent_config` is a dict with agent flags, e.g.:
        {
            "architect": True,  # Always enabled
            "security": False,
            "reliability": True,
            "cost": False,
            ...
        }
        """
        self.architect_agent = None
        if hasattr(agent_source, "agent_client"):
            # We received the AzureArchitectAgent wrapper.
            self.architect_agent = agent_source
            chat_client = agent_source.agent_client
        else:
            chat_client = agent_source

        if not hasattr(chat_client, "create_agent"):
            raise ValueError("Agent client must provide a create_agent method for team orchestration")

        self.chat_client = chat_client
        
        # Default: all agents enabled if no config provided
        if agent_config is None:
            agent_config = {
                "architect": True,
                "security": True,
                "reliability": True,
                "cost": True,
                "networking": True,
                "observability": True,
                "dataStorage": True,
                "compliance": True,
                "identity": True,
                "naming": True,
            }

        # Base writer (Architect) - always enabled
        self.writer = _agent(self.chat_client, "Architect", _writer_instr())

        # Create reviewer agents only if enabled
        self.security = _agent(self.chat_client, "SecurityReviewer", _security_instr()) if agent_config.get("security", False) else None
        self.identity = _agent(self.chat_client, "IdentityGovernanceReviewer", _identity_instr()) if agent_config.get("identity", False) else None
        self.naming = _agent(self.chat_client, "NamingEnforcer", _naming_instr()) if agent_config.get("naming", False) else None
        self.reliab = _agent(self.chat_client, "ReliabilityReviewer", _reliability_instr()) if agent_config.get("reliability", False) else None
        self.networking = _agent(self.chat_client, "NetworkingReviewer", _networking_instr()) if agent_config.get("networking", False) else None
        self.cost = _agent(self.chat_client, "CostPerfOptimizer", _cost_perf_instr()) if agent_config.get("cost", False) else None
        self.comp = _agent(self.chat_client, "ComplianceReviewer", _compliance_instr()) if agent_config.get("compliance", False) else None
        self.observability = _agent(self.chat_client, "ObservabilityReviewer", _observability_instr()) if agent_config.get("observability", False) else None
        self.data_storage = _agent(self.chat_client, "DataStorageReviewer", _data_storage_instr()) if agent_config.get("dataStorage", False) else None
        self.final = _agent(self.chat_client, "FinalEditor", _final_editor_instr())
        
        # Log enabled agents for debugging
        enabled_agents = ["Architect"]
        if self.security:
            enabled_agents.append("SecurityReviewer")
        if self.identity:
            enabled_agents.append("IdentityGovernanceReviewer")
        if self.naming:
            enabled_agents.append("NamingEnforcer")
        if self.reliab:
            enabled_agents.append("ReliabilityReviewer")
        if self.networking:
            enabled_agents.append("NetworkingReviewer")
        if self.cost:
            enabled_agents.append("CostPerfOptimizer")
        if self.comp:
            enabled_agents.append("ComplianceReviewer")
        if self.observability:
            enabled_agents.append("ObservabilityReviewer")
        if self.data_storage:
            enabled_agents.append("DataStorageReviewer")
        enabled_agents.append("FinalEditor")
        logger.info(f"LandingZoneTeam initialized with {len(enabled_agents)} agents: {', '.join(enabled_agents)}")

        # Build sequential pipeline with only enabled agents
        sequential_agents = [self.writer]
        if self.security:
            sequential_agents.append(self.security)
        if self.identity:
            sequential_agents.append(self.identity)
        if self.naming:
            sequential_agents.append(self.naming)
        if self.reliab:
            sequential_agents.append(self.reliab)
        if self.cost:
            sequential_agents.append(self.cost)
        if self.comp:
            sequential_agents.append(self.comp)
        sequential_agents.append(self.final)

        self.seq_workflow = (
            SequentialBuilder()
            .participants(sequential_agents)
            .build()
        )

        # Build concurrent workflow with only enabled parallel reviewers
        concurrent_agents = []
        if self.reliab:
            concurrent_agents.append(self.reliab)
        if self.cost:
            concurrent_agents.append(self.cost)
        if self.networking:
            concurrent_agents.append(self.networking)
        if self.observability:
            concurrent_agents.append(self.observability)
        if self.data_storage:
            concurrent_agents.append(self.data_storage)

        if concurrent_agents:
            self.concurrent_workflow = (
                ConcurrentBuilder()
                .participants(concurrent_agents)
                .build()
            )
        else:
            # No concurrent agents enabled, use empty workflow
            self.concurrent_workflow = None

    async def run_sequential(self, user_prompt: str) -> str:
        last_output: Optional[List[ChatMessage]] = None
        async for ev in self.seq_workflow.run_stream(user_prompt):
            if isinstance(ev, WorkflowOutputEvent):
                last_output = ev.data
        if not last_output:
            return "No output."
        return "\n".join([m.text for m in last_output if m.role in (Role.ASSISTANT,)])

    async def run_with_parallel_pass(self, user_prompt: str) -> str:
        # First draft
        draft = await self.writer.run(user_prompt)
        messages = list(draft.messages)

        # If no concurrent agents enabled, skip parallel pass
        if not self.concurrent_workflow:
            # Run final editor on the draft directly
            final = await self.final.run(messages)
            if hasattr(final, "messages") and final.messages:
                return final.messages[-1].text
            return str(final)

        # Fan-out reviewers on the draft, collect all reviewer outputs
        collected_messages = []
        async for ev in self.concurrent_workflow.run_stream(messages):
            if isinstance(ev, WorkflowOutputEvent):
                data = ev.data
                # ev.data may be a list of ChatMessage, a response object with .messages, or a single message-like object
                if isinstance(data, list):
                    collected_messages.extend(data)
                else:
                    messages_attr = getattr(data, "messages", None)
                    if messages_attr is not None:
                        collected_messages.extend(list(messages_attr))
                        continue
                    collected_messages.append(data)

        # If reviewers produced no output, fall back to the draft's last assistant text
        if not collected_messages:
            return draft.messages[-1].text

        # Run final editor over the combined reviewer outputs
        final = await self.final.run(collected_messages)
        # final might be an object with .messages or a simple string; prefer the last assistant text when available
        if hasattr(final, "messages") and final.messages:
            return final.messages[-1].text
        return str(final)

    @staticmethod
    def _extract_diagram_payload(final_text: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not final_text:
            return None, None
        match = DIAGRAM_SECTION_REGEX.search(final_text)
        if not match:
            return None, None
        raw_json = match.group(1).strip()
        try:
            return json.loads(raw_json), raw_json
        except json.JSONDecodeError as exc:
            logger.warning("LandingZoneTeam failed to parse Diagram JSON: %s", exc)
            return None, raw_json

    async def _generate_iac_bundle(
        self,
        diagram: Optional[Dict[str, Any]],
        narrative: str,
        region: str = "westeurope",
    ) -> Dict[str, Any]:
        """Produce Bicep and Terraform artifacts using the AzureArchitectAgent when available."""
        bundle: Dict[str, Any] = {"bicep": None, "terraform": None}
        agent = self.architect_agent
        if not agent:
            logger.debug("LandingZoneTeam has no architect agent reference; skipping IaC generation.")
            return bundle

        diagram_payload: Dict[str, Any] | None = None
        if isinstance(diagram, dict):
            diagram_payload = diagram

        async def _generate_bicep() -> Optional[Dict[str, Any]]:
            try:
                use_mcp = False
                try:
                    use_mcp = bool(agent.should_use_mcp("bicep"))
                except AttributeError:
                    use_mcp = False
                if diagram_payload and use_mcp:
                    generate_via_mcp = getattr(agent, "generate_bicep_via_mcp", None)
                    if callable(generate_via_mcp):
                        return await generate_via_mcp(diagram_payload, region=region)
                generate_bicep = getattr(agent, "generate_bicep_code", None)
                if callable(generate_bicep):
                    return await generate_bicep({"diagram": diagram_payload})
                generate_bicep = getattr(agent, "generate_bicep_code", None)
                if callable(generate_bicep):
                    return await generate_bicep(narrative)
                logger.warning("LandingZoneTeam could not locate generate_bicep_code on architect agent.")
            except Exception:
                logger.exception("LandingZoneTeam failed to generate Bicep")
                return None

        async def _generate_terraform() -> Optional[Dict[str, Any]]:
            try:
                generate_tf = getattr(agent, "generate_terraform_code", None)
                if not callable(generate_tf):
                    logger.warning("LandingZoneTeam could not locate generate_terraform_code on architect agent.")
                    return None
                if diagram_payload:
                    return await generate_tf({"diagram": diagram_payload})
                return await generate_tf(narrative)
            except Exception:
                logger.exception("LandingZoneTeam failed to generate Terraform")
                return None

        tasks = [
            asyncio.create_task(_generate_bicep()),
            asyncio.create_task(_generate_terraform()),
        ]
        bicep_result, terraform_result = await asyncio.gather(*tasks)

        if bicep_result and isinstance(bicep_result, dict):
            bundle["bicep"] = bicep_result
        if terraform_result and isinstance(terraform_result, dict):
            bundle["terraform"] = terraform_result

        logger.debug(
            "LandingZoneTeam IaC bundle generated: bicep=%s terraform=%s",
            "yes" if bundle["bicep"] else "no",
            "yes" if bundle["terraform"] else "no",
        )
        return bundle

    async def _diagram_from_iac(
        self, narrative: str, iac_bundle: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        agent = self.architect_agent
        if not agent:
            return None, None
        chat_agent = getattr(agent, "chat_agent", None)
        if not chat_agent:
            return None, None

        bicep_template = None
        terraform_template = None
        bicep_payload = iac_bundle.get("bicep") if isinstance(iac_bundle, dict) else None
        terraform_payload = iac_bundle.get("terraform") if isinstance(iac_bundle, dict) else None
        if isinstance(bicep_payload, dict):
            bicep_template = bicep_payload.get("bicep_code") or bicep_payload.get("content")
        if isinstance(terraform_payload, dict):
            terraform_template = terraform_payload.get("terraform_code") or terraform_payload.get("content")

        source_snippet = None
        source_language = None
        if isinstance(bicep_template, str) and bicep_template.strip():
            source_snippet = bicep_template.strip()
            source_language = "bicep"
        elif isinstance(terraform_template, str) and terraform_template.strip():
            source_snippet = terraform_template.strip()
            source_language = "terraform"

        if not source_snippet:
            return None, None

        prompt = (
            "You are an Azure architecture cartographer. Convert the following IaC template into the structured "
            "ReactFlow diagram JSON used by the canvas. Follow the schema and hierarchy guidance exactly.\n\n"
            f"{STRUCTURED_DIAGRAM_GUIDANCE}\n"
            "The IaC template:\n"
            f"```{source_language}\n{source_snippet}\n```\n\n"
            "Return ONLY the JSON object (no commentary) that conforms to the schema."
        )

        try:
            response = await chat_agent.run(prompt)
            text = getattr(response, "result", None)
            if not isinstance(text, str):
                text = getattr(response, "text", None) or str(response)
            if not isinstance(text, str):
                return None, None

            # Extract JSON payload from response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end <= start:
                return None, None
            json_blob = text[start:end]
            parsed = json.loads(json_blob)
            if not isinstance(parsed, dict):
                return None, None
            raw_json = json.dumps(parsed, indent=2)
            return parsed, raw_json
        except Exception as exc:
            logger.warning("Failed to derive diagram from IaC: %s", exc)
            return None, None

    @staticmethod
    def _inject_diagram_section(report: str, raw_json: str) -> str:
        payload = f"Diagram JSON\n```json\n{raw_json}\n```"
        if DIAGRAM_SECTION_REGEX.search(report or ""):
            return DIAGRAM_SECTION_REGEX.sub(payload, report, count=1)
        return f"{report.rstrip()}\n\n{payload}"
    
    async def _run_agent_streamed(self, run_id: str, step_idx: int, total: int, agent, input_messages, meta=None) -> str:
        if agent is None:
            raise RuntimeError("Agent is not enabled but was scheduled to run (NoneType). Check agent_config flags.")
        start_ts = time.time()
        name = getattr(agent, "name", "Agent")
        step_id = str(step_idx)

        logger.info("[team-stream][%s] starting step %s/%s", name, step_idx, total)
        print(f"[TRACE] {name} start {step_idx}", flush=True)
        await tracer.emit(TraceEvent(
            run_id=run_id, step_id=step_id, agent=name, phase="start",
            ts=time.time(), meta=meta or {}, progress={"current": step_idx, "total": total},
            telemetry={"tokens_in": 0, "tokens_out": 0, "latency_ms": 0}
        ))

        out_text: list[str] = []
        last_response_text: str | None = None
        tokens_out = 0
        last_heartbeat = time.time()
        heartbeat_interval = 5.0  # Send progress updates every 5 seconds

        try:
            async for chunk in agent.run_stream(input_messages):
                # Log chunk details for debugging
                print(f"[TEAM-STREAM][{name}] Chunk type: {type(chunk).__name__}", flush=True)
                if hasattr(chunk, '__dict__'):
                    print(f"[TEAM-STREAM][{name}] Chunk attrs: {list(chunk.__dict__.keys())[:10]}", flush=True)
                
                # Send heartbeat updates for long-running reasoning models
                now = time.time()
                if now - last_heartbeat > heartbeat_interval:
                    await tracer.emit(TraceEvent(
                        run_id=run_id, step_id=step_id, agent=name, phase="thinking",
                        ts=now, meta=meta or {}, progress={"current": step_idx, "total": total},
                        telemetry={"tokens_in": 0, "tokens_out": 0, "latency_ms": int((now - start_ts) * 1000)},
                        message_delta=f"[{name} is analyzing and reasoning...]"
                    ))
                    last_heartbeat = now
                text_payloads: list[str] = []

                # Check for text attribute first (like in stream_chat)
                if hasattr(chunk, 'text') and chunk.text:
                    text = str(chunk.text)
                    text_payloads.append(text)
                    print(f"[TEAM-STREAM][{name}] ✓ Extracted from .text: {repr(text[:50])}", flush=True)

                delta = getattr(chunk, "delta", None)
                if delta:
                    if isinstance(delta, str) and delta.strip():
                        text_payloads.append(delta)
                    else:
                        candidate = getattr(delta, "text", None) or getattr(delta, "content", None)
                        if isinstance(candidate, str) and candidate.strip():
                            text_payloads.append(candidate)

                # Some clients stream ChatMessage objects via messages attribute
                messages_attr = getattr(chunk, "messages", None)
                if messages_attr:
                    try:
                        for msg in messages_attr:
                            candidate = getattr(msg, "text", None) or getattr(msg, "content", None)
                            if isinstance(candidate, str) and candidate.strip():
                                text_payloads.append(candidate)
                    except TypeError:
                        # Not iterable; ignore
                        pass

                # Capture full responses when provided for later fallback
                response_attr = getattr(chunk, "response", None)
                if response_attr is not None:
                    # Prefer explicit result property when present
                    candidate = getattr(response_attr, "result", None)
                    if isinstance(candidate, str) and candidate.strip():
                        last_response_text = candidate
                    # Otherwise look for messages collection
                    messages = getattr(response_attr, "messages", None)
                    if messages:
                        try:
                            collected = []
                            for msg in messages:
                                msg_text = getattr(msg, "text", None) or getattr(msg, "content", None)
                                if isinstance(msg_text, str) and msg_text.strip():
                                    collected.append(msg_text)
                            if collected:
                                last_response_text = "\n".join(collected)
                        except TypeError:
                            pass

                # Fallback for dict-based chunks
                if not text_payloads and isinstance(chunk, dict):
                    candidate = chunk.get("delta") or chunk.get("text") or chunk.get("content")
                    if isinstance(candidate, str) and candidate.strip():
                        text_payloads.append(candidate)

                for text in text_payloads:
                    out_text.append(text)
                    tokens_out += len(text.split())  # lightweight proxy
                    print(f"[TRACE] {name} delta {step_idx}", flush=True)
                    try:
                        _short = _shorten_for_tracing(text, 500) or ''
                        logger.info("[team-stream][%s][delta] %s", name, _short.replace("\n", "\\n")[:500])
                    except Exception:
                        logger.debug("Failed to log streaming delta for %s", name, exc_info=True)
                    _trace_short = _shorten_for_tracing(text) or (str(text)[:1200] if text else None)
                    await tracer.emit(TraceEvent(
                        run_id=run_id, step_id=step_id, agent=name, phase="delta",
                        ts=time.time(), meta=meta or {}, progress={"current": step_idx, "total": total},
                        telemetry={"tokens_in": 0, "tokens_out": tokens_out, "latency_ms": int((time.time()-start_ts)*1000)},
                        message_delta=_trace_short
                    ))
        except Exception as e:
            await tracer.emit(TraceEvent(
                run_id=run_id, step_id=step_id, agent=name, phase="error",
                ts=time.time(), meta=meta or {}, progress={"current": step_idx, "total": total},
                telemetry={"tokens_in": 0, "tokens_out": tokens_out, "latency_ms": int((time.time()-start_ts)*1000)},
                error=str(e)
            ))
            raise

        final = "".join(out_text)
        if not final and last_response_text:
            final = last_response_text
        if not final:
            run_fn = getattr(agent, "run", None)
            if callable(run_fn):
                try:
                    result = run_fn(input_messages)
                    if inspect.isawaitable(result):
                        result = await result
                    candidate = getattr(result, "result", None)
                    if isinstance(candidate, str) and candidate.strip():
                        final = candidate
                    elif isinstance(result, str) and result.strip():
                        final = result
                    else:
                        messages = getattr(result, "messages", None)
                        if messages:
                            collected = []
                            for msg in messages:
                                msg_text = getattr(msg, "text", None) or getattr(msg, "content", None)
                                if isinstance(msg_text, str) and msg_text.strip():
                                    collected.append(msg_text)
                            if collected:
                                final = "\n".join(collected)
                except Exception:
                    # Ignore fallback failures- streaming result already handled
                    pass

        if (not out_text) and isinstance(final, str) and final.strip():
            tokens_out += len(final.split())
            _trace_short_final = _shorten_for_tracing(final) or (str(final)[:1200] if final else None)
            await tracer.emit(TraceEvent(
                run_id=run_id,
                step_id=step_id,
                agent=name,
                phase="delta",
                ts=time.time(),
                meta=meta or {},
                progress={"current": step_idx, "total": total},
                telemetry={
                    "tokens_in": 0,
                    "tokens_out": tokens_out,
                    "latency_ms": int((time.time() - start_ts) * 1000),
                },
                message_delta=_trace_short_final,
            ))

        print(f"[TRACE] {name} end {step_idx}", flush=True)
        await tracer.emit(TraceEvent(
            run_id=run_id, step_id=step_id, agent=name, phase="end",
            ts=time.time(), meta=meta or {}, progress={"current": step_idx, "total": total},
            telemetry={"tokens_in": 0, "tokens_out": tokens_out, "latency_ms": int((time.time()-start_ts)*1000)},
            summary=f"{name} completed"
        ))
        logger.info("[team-stream][%s] completed step %s/%s", name, step_idx, total)
        # Redact any embedded guidance before returning to callers / downstream pipelines
        final = _redact_guidance(final) or ''
        return final

    async def run_sequential_traced(
        self, user_prompt: str, run_id: Optional[str] = None
    ) -> Tuple[str, Optional[Dict[str, Any]], Optional[str], Dict[str, Any], str]:
        run_id = run_id or tracer.new_run()
        tracer.ensure_run(run_id)
        # Sequential pipeline now: Architect + Security + Identity + Naming + Reliability + Cost + Compliance + FinalEditor
        pipeline = [
            self.writer,
            self.security,
            self.identity,
            self.naming,
            self.reliab,
            self.cost,
            self.comp,
            self.final,
        ]
        pipeline = [ag for ag in pipeline if ag is not None]
        messages = user_prompt
        outputs = []
        waf_map = [
            "-",
            "Security",
            "Identity & Governance",
            "Operational Excellence",
            "Reliability",
            "Cost Optimization",
            "Compliance",
            "-",
        ]

        for i, ag in enumerate(pipeline, start=1):
            out = await self._run_agent_streamed(
                run_id,
                i,
                len(pipeline),
                ag,
                messages,
                meta={"waf_pillar": waf_map[i - 1] if i - 1 < len(waf_map) else "-"},
            )
            messages = out  # pass to next
            outputs.append(out)

        final_text = outputs[-1] if outputs else "No output."
        diagram_dict, raw_json = self._extract_diagram_payload(final_text)
        iac_bundle = await self._generate_iac_bundle(diagram_dict, final_text)
        derived_diagram, derived_raw = await self._diagram_from_iac(final_text, iac_bundle)
        if derived_diagram:
            diagram_dict = derived_diagram
            raw_json = derived_raw
            if raw_json:
                final_text = self._inject_diagram_section(final_text, raw_json)
        # Redact any embedded guidance before returning payloads to callers/UI
        final_text = _redact_guidance(final_text) or final_text
        return final_text, diagram_dict, raw_json, iac_bundle, run_id

    async def run_parallel_pass_traced(
        self, user_prompt: str, run_id: Optional[str] = None
    ) -> Tuple[str, Optional[Dict[str, Any]], Optional[str], Dict[str, Any], str]:
        run_id = run_id or tracer.new_run()
        tracer.ensure_run(run_id)
        # Build enabled parallel reviewers
        parallel_reviewers = [
            self.reliab,
            self.cost,
            self.networking,
            self.observability,
            self.data_storage,
        ]
        parallel_reviewers = [ag for ag in parallel_reviewers if ag is not None]
        total_steps = 1 + len(parallel_reviewers) + 1

        # First draft
        draft = await self._run_agent_streamed(run_id, 1, total_steps, self.writer, user_prompt, meta={"waf_pillar": "-"})

        # Fan-out reviewers (reliability, cost, networking, observability, data/storage)
        async def _run_reviewer(idx, ag, meta):
            return await self._run_agent_streamed(run_id, idx, total_steps, ag, draft, meta=meta)

        results = []
        if parallel_reviewers:
            gathered = await asyncio.gather(
                *[
                    _run_reviewer(idx + 2, ag, {"parallel_group": "fanout-1", "waf_pillar": "parallel"})
                    for idx, ag in enumerate(parallel_reviewers)
                ]
            )
            results.extend(gathered)

        merged_input = "\n\n---\n\n".join(results) if results else draft
        final = await self._run_agent_streamed(run_id, total_steps, total_steps, self.final, merged_input, meta={"aggregator": "FinalEditor"})
        diagram_dict, raw_json = self._extract_diagram_payload(final)
        iac_bundle = await self._generate_iac_bundle(diagram_dict, final)
        derived_diagram, derived_raw = await self._diagram_from_iac(final, iac_bundle)
        if derived_diagram:
            diagram_dict = derived_diagram
            raw_json = derived_raw
            if raw_json:
                final = self._inject_diagram_section(final, raw_json)
        # Redact before returning
        final = _redact_guidance(final) or final
        return final, diagram_dict, raw_json, iac_bundle, run_id
