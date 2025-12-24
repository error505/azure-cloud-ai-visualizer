"""
Full Architecture Autopilot Engine

Transforms natural language requirements into complete Azure architectures:
1. NLP parsing: Extract services, constraints, compliance needs
2. Multi-agent orchestration: Landing Zone + Security + Cost + Network teams
3. Complete diagram generation: Fully connected architecture with IaC
4. Refinement loop: Allow users to adjust and regenerate

This is the "magic button" that takes: "Build me a compliant e-commerce platform"
and outputs: Complete architecture with 40+ services, proper networking, security, IaC code.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ParsedRequirements:
    """Structured requirements extracted from natural language."""
    workload_type: str  # e-commerce, data-analytics, ml-training, web-app, etc.
    services_needed: List[str]  # Explicit Azure services mentioned
    compliance_frameworks: List[str]  # ISO 27001, SOC 2, HIPAA, PCI-DSS, GDPR
    budget_constraint: Optional[float]  # Monthly budget in USD
    performance_requirements: Dict[str, Any]  # SLAs, latency, throughput
    data_requirements: Dict[str, Any]  # Storage size, retention, sensitivity
    scale_requirements: Dict[str, Any]  # Users, transactions, regions
    integration_requirements: List[str]  # External systems to integrate
    raw_requirements: str  # Original text


class AutopilotEngine:
    """
    Orchestrates multi-agent architecture generation from requirements.
    """
    
    def __init__(self, agent_client):
        """
        Initialize with agent client (supports create_agent()).
        
        Args:
            agent_client: Azure AI, OpenAI, or local model client
        """
        self.agent_client = agent_client
        self.parser_agent = None
        
    async def initialize(self):
        """Create the requirements parser agent."""
        logger.info("Initializing Autopilot Engine...")
        
        parser_instructions = """You are a requirements analyst that extracts structured information from natural language.

Your task: Parse architecture requirements and return JSON with:

{
  "workload_type": "<e-commerce|data-analytics|ml-training|web-app|api-backend|iot|real-time|batch-processing|etc>",
  "services_needed": ["Azure Service 1", "Azure Service 2", ...],
  "compliance_frameworks": ["ISO 27001", "SOC 2", "HIPAA", "PCI-DSS", "GDPR"],
  "budget_constraint": <monthly USD or null>,
  "performance_requirements": {
    "sla_uptime": "99.9%",
    "max_latency_ms": 200,
    "expected_throughput": "10000 req/sec"
  },
  "data_requirements": {
    "storage_size_gb": 5000,
    "retention_years": 7,
    "data_sensitivity": "confidential|internal|public"
  },
  "scale_requirements": {
    "concurrent_users": 50000,
    "transactions_per_day": 1000000,
    "regions": ["West Europe", "East US"]
  },
  "integration_requirements": ["Salesforce", "SAP", "Stripe", etc]
}

Examples of workload detection:
- "Build an e-commerce platform" → workload_type: "e-commerce"
- "I need ML model training infrastructure" → workload_type: "ml-training"
- "Create a real-time analytics dashboard" → workload_type: "real-time-analytics"
- "Build a REST API backend" → workload_type: "api-backend"

Extract ONLY what's explicitly mentioned. Use null for missing info. Return ONLY valid JSON.
"""
        
        try:
            self.parser_agent = self.agent_client.create_agent(
                name="RequirementsParser",
                instructions=parser_instructions
            )
            logger.info("Autopilot requirements parser initialized")
        except Exception as e:
            logger.error(f"Failed to initialize parser agent: {e}")
            raise
    
    async def parse_requirements(self, requirements_text: str) -> ParsedRequirements:
        """
        Parse natural language requirements into structured format.
        
        Args:
            requirements_text: Natural language description
            
        Returns:
            ParsedRequirements with extracted information
        """
        if not self.parser_agent:
            await self.initialize()
        
        prompt = f"""Parse these architecture requirements:

{requirements_text}

Return JSON with extracted requirements."""

        logger.info("Parsing requirements...")
        response = await self.parser_agent.run(prompt)
        response_text = getattr(response, "result", str(response))
        
        # Extract JSON from response
        parsed_data = self._extract_json(response_text)
        if not parsed_data:
            raise ValueError("Failed to parse requirements - no valid JSON returned")
        
        # Convert to dataclass
        # Normalize parsed values to avoid None when keys are present but null
        services_needed = parsed_data.get('services_needed') or []
        compliance_frameworks = parsed_data.get('compliance_frameworks') or []
        integration_requirements = parsed_data.get('integration_requirements') or []
        performance_requirements = parsed_data.get('performance_requirements') or {}
        data_requirements = parsed_data.get('data_requirements') or {}
        scale_requirements = parsed_data.get('scale_requirements') or {}

        parsed = ParsedRequirements(
            workload_type=parsed_data.get('workload_type', 'unknown'),
            services_needed=services_needed,
            compliance_frameworks=compliance_frameworks,
            budget_constraint=parsed_data.get('budget_constraint'),
            performance_requirements=performance_requirements,
            data_requirements=data_requirements,
            scale_requirements=scale_requirements,
            integration_requirements=integration_requirements,
            raw_requirements=requirements_text
        )

        # Safe logging (handle empty or missing lists)
        logger.info(
            "Parsed requirements: workload=%s, services=%d, compliance=%s",
            parsed.workload_type,
            len(parsed.services_needed or []),
            parsed.compliance_frameworks or []
        )
        
        return parsed
    
    async def generate_complete_architecture(
        self,
        requirements: ParsedRequirements,
        use_parallel_pass: bool = True
    ) -> Dict[str, Any]:
        """
        Generate complete architecture from parsed requirements.
        
        Uses the Landing Zone Team (already exists) for multi-agent orchestration.
        
        Args:
            requirements: Parsed requirements
            use_parallel_pass: Use parallel agent review (faster, more thorough)
            
        Returns:
            Complete architecture with diagram, IaC, cost estimates, compliance info
        """
        from app.agents.landing_zone_team import LandingZoneTeam
        
        # Build enriched prompt for Landing Zone Team
        enriched_prompt = self._build_enriched_prompt(requirements)
        
        logger.info(f"Generating architecture for {requirements.workload_type} workload...")
        
        # Create Landing Zone Team (uses existing multi-agent infrastructure)
        # Autopilot uses full team with all agents enabled
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
        team = LandingZoneTeam(self.agent_client, agent_config=agent_config)
        
        # Run architecture generation with tracing
        if use_parallel_pass:
            (
                final_text,
                diagram_dict,
                raw_json,
                iac_bundle,
                run_id
            ) = await team.run_parallel_pass_traced(enriched_prompt)
        else:
            (
                final_text,
                diagram_dict,
                raw_json,
                iac_bundle,
                run_id
            ) = await team.run_sequential_traced(enriched_prompt)
        
        # Extract cost estimate from final text
        cost_estimate = self._extract_cost_estimate(final_text)
        
        # Build response
        result = {
            'diagram': diagram_dict,
            'diagram_json': raw_json,
            'architecture_description': final_text,
            'iac': iac_bundle,
            'cost_estimate': cost_estimate,
            'compliance_frameworks': requirements.compliance_frameworks,
            'run_id': run_id,
            'workload_type': requirements.workload_type,
            'services_count': len(diagram_dict.get('nodes', [])) if diagram_dict else 0
        }
        
        logger.info(f"Architecture generation complete. Services: {result['services_count']}, Run ID: {run_id}")
        
        return result
    
    def _build_enriched_prompt(self, requirements: ParsedRequirements) -> str:
        """Build detailed prompt for Landing Zone Team."""
        
        prompt_parts = [
            "# Architecture Requirements",
            "",
            f"**Workload Type:** {requirements.workload_type}",
            "",
            f"**Original Requirements:**",
            requirements.raw_requirements,
            "",
        ]
        
        if requirements.services_needed:
            prompt_parts.extend([
                "**Required Azure Services:**",
                ", ".join(requirements.services_needed),
                "",
            ])
        
        if requirements.compliance_frameworks:
            prompt_parts.extend([
                "**Compliance Requirements:**",
                f"Must comply with: {', '.join(requirements.compliance_frameworks)}",
                "- Ensure audit logging is enabled on all services",
                "- Implement data encryption at rest and in transit",
                "- Add proper access controls and RBAC",
                "- Include diagnostic settings for compliance monitoring",
                "",
            ])
        
        if requirements.budget_constraint:
            prompt_parts.extend([
                "**Budget Constraint:**",
                f"Monthly budget: ${requirements.budget_constraint:,.2f}",
                "- Optimize for cost efficiency",
                "- Consider reserved instances where appropriate",
                "- Use appropriate SKU tiers (avoid over-provisioning)",
                "",
            ])
        
        if requirements.performance_requirements:
            perf = requirements.performance_requirements
            prompt_parts.append("**Performance Requirements:**")
            if perf.get('sla_uptime'):
                prompt_parts.append(f"- SLA: {perf['sla_uptime']} uptime")
            if perf.get('max_latency_ms'):
                prompt_parts.append(f"- Max latency: {perf['max_latency_ms']}ms")
            if perf.get('expected_throughput'):
                prompt_parts.append(f"- Throughput: {perf['expected_throughput']}")
            prompt_parts.append("")
        
        if requirements.data_requirements:
            data = requirements.data_requirements
            prompt_parts.append("**Data Requirements:**")
            if data.get('storage_size_gb'):
                prompt_parts.append(f"- Storage: {data['storage_size_gb']:,} GB")
            if data.get('retention_years'):
                prompt_parts.append(f"- Retention: {data['retention_years']} years")
            if data.get('data_sensitivity'):
                prompt_parts.append(f"- Data classification: {data['data_sensitivity']}")
            prompt_parts.append("")
        
        if requirements.scale_requirements:
            scale = requirements.scale_requirements
            prompt_parts.append("**Scale Requirements:**")
            if scale.get('concurrent_users'):
                prompt_parts.append(f"- Concurrent users: {scale['concurrent_users']:,}")
            if scale.get('transactions_per_day'):
                prompt_parts.append(f"- Daily transactions: {scale['transactions_per_day']:,}")
            if scale.get('regions'):
                regions = scale['regions']
                if isinstance(regions, list):
                    prompt_parts.append(f"- Regions: {', '.join(regions)}")
            prompt_parts.append("")
        
        if requirements.integration_requirements:
            prompt_parts.extend([
                "**External Integrations:**",
                ", ".join(requirements.integration_requirements),
                "",
            ])
        
        prompt_parts.extend([
            "---",
            "",
            "Design a COMPLETE, PRODUCTION-READY Azure architecture that satisfies ALL requirements above.",
            "Include proper networking (VNets, NSGs, private endpoints), security (Key Vault, Managed Identities),",
            "monitoring (Application Insights, Log Analytics), and backup/DR where appropriate.",
            "",
            "The architecture should be enterprise-grade and follow Azure Well-Architected Framework principles.",
        ])
        
        return "\n".join(prompt_parts)
    
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from agent response."""
        try:
            # Try direct parse
            return json.loads(text)
        except json.JSONDecodeError:
            # Extract from code blocks
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # Find JSON object boundaries
            start = text.find('{')
            if start == -1:
                return None
            
            depth = 0
            for i, ch in enumerate(text[start:]):
                if ch == '{':
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:start + i + 1])
                        except json.JSONDecodeError:
                            return None
            
            return None
    
    def _extract_cost_estimate(self, architecture_text: str) -> Optional[Dict[str, Any]]:
        """Extract cost estimates from architecture description."""
        # Look for cost-related patterns in the text
        patterns = [
            r'estimated.*?\$?(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:USD|dollars?)?.*?(?:per\s+)?month',
            r'monthly\s+cost.*?\$?(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)\s*\/?\s*month',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, architecture_text, re.IGNORECASE)
            if match:
                cost_str = match.group(1).replace(',', '')
                try:
                    monthly_cost = float(cost_str)
                    return {
                        'currency': 'USD',
                        'monthly_total': monthly_cost,
                        'annual_total': monthly_cost * 12,
                        'note': 'Estimated based on architecture description'
                    }
                except ValueError:
                    pass
        
        return None


async def create_autopilot_engine(agent_client) -> AutopilotEngine:
    """
    Factory function to create and initialize AutopilotEngine.
    
    Args:
        agent_client: Azure AI, OpenAI, or local model client
        
    Returns:
        Initialized AutopilotEngine instance
    """
    engine = AutopilotEngine(agent_client)
    await engine.initialize()
    return engine
