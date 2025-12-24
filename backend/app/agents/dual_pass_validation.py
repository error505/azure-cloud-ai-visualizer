"""
Dual-Pass Validation System

Implements the Architect vs Critic validation pattern where:
1. Architect Agent generates architecture proposals
2. Critic Agent reviews for security, cost, reliability, compliance issues
3. System presents both views with conflict resolution

This creates a powerful validation workflow that catches issues before deployment.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Represents a single issue found by the Critic."""
    severity: str  # critical, high, medium, low
    category: str  # security, cost, reliability, compliance, performance
    title: str
    description: str
    affected_services: List[str]  # Node IDs affected
    recommendation: str
    auto_fixable: bool


@dataclass
class ArchitectProposal:
    """Architect's proposed architecture."""
    diagram: Dict[str, Any]
    rationale: str
    services_count: int
    estimated_monthly_cost: Optional[float]
    compliance_frameworks: List[str]


@dataclass
class CriticReview:
    """Critic's review of the Architect's proposal."""
    overall_score: int  # 0-100
    issues: List[ValidationIssue]
    strengths: List[str]
    summary: str
    recommended_changes: Dict[str, Any]  # Suggested diagram modifications


@dataclass
class DualPassResult:
    """Combined result from both agents."""
    architect_proposal: ArchitectProposal
    critic_review: CriticReview
    conflicts: List[Dict[str, Any]]
    final_recommendation: str
    auto_fix_available: bool


class DualPassValidator:
    """
    Orchestrates dual-pass validation between Architect and Critic agents.
    """
    
    def __init__(self, agent_client):
        """
        Initialize with agent client (Azure AI or OpenAI).
        
        Args:
            agent_client: Chat client supporting create_agent()
        """
        self.agent_client = agent_client
        self.architect_agent = None
        self.critic_agent = None
        
    async def initialize(self):
        """Create Architect and Critic agents."""
        logger.info("Initializing Dual-Pass Validation agents...")
        
        # Architect: Focuses on creating well-architected solutions
        architect_instructions = """You are an Azure Solutions Architect focused on creating optimal architectures.

Your responsibilities:
1. Design architectures that meet functional requirements
2. Select appropriate Azure services for each use case
3. Ensure proper connectivity and data flows
4. Optimize for performance and scalability
5. Consider cost implications
6. Document design rationale

When analyzing requirements or existing diagrams:
- Propose the BEST possible architecture
- Explain WHY you chose each service
- Highlight design trade-offs
- Provide cost estimates
- Note compliance considerations

Return responses as JSON with:
{
  "diagram": { "nodes": [], "edges": [], "groups": [] },
  "rationale": "detailed explanation",
  "services_count": <number>,
  "estimated_monthly_cost": <number or null>,
  "compliance_frameworks": ["ISO 27001", "SOC 2", etc]
}
"""
        
        # Critic: Focuses on finding flaws and risks
        critic_instructions = """You are an Azure Architecture Critic focused on identifying risks and flaws.

Your responsibilities:
1. Review architectures for security vulnerabilities
2. Identify cost optimization opportunities
3. Find reliability and availability issues
4. Check compliance with best practices
5. Detect performance bottlenecks
6. Suggest concrete improvements

Evaluation categories:
- SECURITY: authentication, authorization, encryption, network isolation, secrets management
- COST: oversized resources, unused resources, missing reservations, inefficient patterns
- RELIABILITY: single points of failure, missing backups, no redundancy, poor DR
- COMPLIANCE: missing audit logs, data residency, encryption requirements
- PERFORMANCE: inefficient data flows, missing caching, poor service placement

For EACH issue found, determine if it's auto-fixable (e.g., adding NSG, enabling encryption, adding backup).

Return responses as JSON with:
{
  "overall_score": <0-100>,
  "issues": [
    {
      "severity": "critical|high|medium|low",
      "category": "security|cost|reliability|compliance|performance",
      "title": "brief title",
      "description": "detailed description",
      "affected_services": ["node-id-1", "node-id-2"],
      "recommendation": "specific fix",
      "auto_fixable": true|false
    }
  ],
  "strengths": ["positive aspect 1", "positive aspect 2"],
  "summary": "overall assessment",
  "recommended_changes": {
    "add_nodes": [...],
    "modify_nodes": [...],
    "add_edges": [...],
    "remove_nodes": [...]
  }
}
"""
        
        try:
            self.architect_agent = self.agent_client.create_agent(
                name="ArchitectAgent",
                instructions=architect_instructions
            )
            
            self.critic_agent = self.agent_client.create_agent(
                name="CriticAgent", 
                instructions=critic_instructions
            )
            
            logger.info("Dual-Pass Validation agents initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize agents: {e}")
            raise
    
    async def validate_requirements(
        self, 
        requirements: str,
        context: Optional[Dict[str, Any]] = None
    ) -> DualPassResult:
        """
        Validate architecture requirements through dual-pass process.
        
        Args:
            requirements: Natural language requirements
            context: Optional context (budget, compliance needs, etc)
            
        Returns:
            DualPassResult with both agent outputs and conflicts
        """
        if not self.architect_agent or not self.critic_agent:
            await self.initialize()
        
        # Phase 1: Architect proposes solution
        architect_prompt = f"""Design an Azure architecture for these requirements:

{requirements}

Context: {json.dumps(context or {}, indent=2)}

Provide your complete architectural proposal as JSON."""

        logger.info("Running Architect agent...")
        architect_response = await self.architect_agent.run(architect_prompt)
        architect_text = getattr(architect_response, "result", str(architect_response))
        
        # Parse architect response
        architect_data = self._extract_json(architect_text)
        if not architect_data:
            raise ValueError("Architect failed to return valid JSON")
        
        architect_proposal = ArchitectProposal(
            diagram=architect_data.get("diagram", {}),
            rationale=architect_data.get("rationale", ""),
            services_count=architect_data.get("services_count", 0),
            estimated_monthly_cost=architect_data.get("estimated_monthly_cost"),
            compliance_frameworks=architect_data.get("compliance_frameworks", [])
        )
        
        # Phase 2: Critic reviews the proposal
        critic_prompt = f"""Review this Azure architecture proposal and identify ALL issues:

ORIGINAL REQUIREMENTS:
{requirements}

ARCHITECT'S PROPOSAL:
{json.dumps(architect_data, indent=2)}

Perform a thorough review covering security, cost, reliability, compliance, and performance.
Return your complete review as JSON."""

        logger.info("Running Critic agent...")
        critic_response = await self.critic_agent.run(critic_prompt)
        critic_text = getattr(critic_response, "result", str(critic_response))
        
        # Parse critic response
        critic_data = self._extract_json(critic_text)
        if not critic_data:
            raise ValueError("Critic failed to return valid JSON")
        
        # Convert issues to dataclass instances
        issues = []
        for issue_dict in critic_data.get("issues", []):
            issues.append(ValidationIssue(
                severity=issue_dict.get("severity", "medium"),
                category=issue_dict.get("category", "general"),
                title=issue_dict.get("title", ""),
                description=issue_dict.get("description", ""),
                affected_services=issue_dict.get("affected_services", []),
                recommendation=issue_dict.get("recommendation", ""),
                auto_fixable=issue_dict.get("auto_fixable", False)
            ))
        
        critic_review = CriticReview(
            overall_score=critic_data.get("overall_score", 0),
            issues=issues,
            strengths=critic_data.get("strengths", []),
            summary=critic_data.get("summary", ""),
            recommended_changes=critic_data.get("recommended_changes", {})
        )
        
        # Phase 3: Identify conflicts and generate recommendation
        conflicts = self._identify_conflicts(architect_proposal, critic_review)
        final_recommendation = self._generate_final_recommendation(
            architect_proposal, 
            critic_review, 
            conflicts
        )
        auto_fix_available = any(issue.auto_fixable for issue in issues)
        
        return DualPassResult(
            architect_proposal=architect_proposal,
            critic_review=critic_review,
            conflicts=conflicts,
            final_recommendation=final_recommendation,
            auto_fix_available=auto_fix_available
        )
    
    async def validate_existing_diagram(
        self,
        diagram: Dict[str, Any],
        requirements: Optional[str] = None
    ) -> DualPassResult:
        """
        Validate an existing diagram through dual-pass process.
        
        Args:
            diagram: ReactFlow diagram with nodes/edges/groups
            requirements: Optional original requirements
            
        Returns:
            DualPassResult with validation findings
        """
        if not self.architect_agent or not self.critic_agent:
            await self.initialize()
        
        # Phase 1: Architect reviews and potentially improves
        architect_prompt = f"""Review this existing Azure architecture diagram:

{json.dumps(diagram, indent=2)}

{"Original requirements: " + requirements if requirements else ""}

Analyze the current design and propose any improvements. Return JSON."""

        logger.info("Architect reviewing existing diagram...")
        architect_response = await self.architect_agent.run(architect_prompt)
        architect_text = getattr(architect_response, "result", str(architect_response))
        
        architect_data = self._extract_json(architect_text)
        if not architect_data:
            raise ValueError("Architect failed to return valid JSON")
        
        architect_proposal = ArchitectProposal(
            diagram=architect_data.get("diagram", diagram),  # Fallback to original
            rationale=architect_data.get("rationale", ""),
            services_count=architect_data.get("services_count", len(diagram.get("nodes", []))),
            estimated_monthly_cost=architect_data.get("estimated_monthly_cost"),
            compliance_frameworks=architect_data.get("compliance_frameworks", [])
        )
        
        # Phase 2: Critic reviews
        critic_prompt = f"""Perform a comprehensive security, cost, reliability, and compliance audit:

CURRENT ARCHITECTURE:
{json.dumps(diagram, indent=2)}

{"Requirements context: " + requirements if requirements else ""}

Identify ALL issues and provide specific recommendations. Return JSON."""

        logger.info("Critic auditing diagram...")
        critic_response = await self.critic_agent.run(critic_prompt)
        critic_text = getattr(critic_response, "result", str(critic_response))
        
        critic_data = self._extract_json(critic_text)
        if not critic_data:
            raise ValueError("Critic failed to return valid JSON")
        
        issues = []
        for issue_dict in critic_data.get("issues", []):
            issues.append(ValidationIssue(
                severity=issue_dict.get("severity", "medium"),
                category=issue_dict.get("category", "general"),
                title=issue_dict.get("title", ""),
                description=issue_dict.get("description", ""),
                affected_services=issue_dict.get("affected_services", []),
                recommendation=issue_dict.get("recommendation", ""),
                auto_fixable=issue_dict.get("auto_fixable", False)
            ))
        
        critic_review = CriticReview(
            overall_score=critic_data.get("overall_score", 0),
            issues=issues,
            strengths=critic_data.get("strengths", []),
            summary=critic_data.get("summary", ""),
            recommended_changes=critic_data.get("recommended_changes", {})
        )
        
        conflicts = self._identify_conflicts(architect_proposal, critic_review)
        final_recommendation = self._generate_final_recommendation(
            architect_proposal,
            critic_review,
            conflicts
        )
        auto_fix_available = any(issue.auto_fixable for issue in issues)
        
        return DualPassResult(
            architect_proposal=architect_proposal,
            critic_review=critic_review,
            conflicts=conflicts,
            final_recommendation=final_recommendation,
            auto_fix_available=auto_fix_available
        )
    
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from agent response."""
        try:
            # Try direct parse first
            return json.loads(text)
        except json.JSONDecodeError:
            # Extract from code blocks
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass
            
            # Try finding JSON object boundaries
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
    
    def _identify_conflicts(
        self,
        architect_proposal: ArchitectProposal,
        critic_review: CriticReview
    ) -> List[Dict[str, Any]]:
        """
        Identify conflicts between Architect's design and Critic's findings.
        
        Returns list of conflict objects with details.
        """
        conflicts = []
        
        # Critical and high severity issues are always conflicts
        for issue in critic_review.issues:
            if issue.severity in ["critical", "high"]:
                conflicts.append({
                    "type": "severity_conflict",
                    "severity": issue.severity,
                    "category": issue.category,
                    "issue_title": issue.title,
                    "architect_rationale": architect_proposal.rationale,
                    "critic_concern": issue.description,
                    "recommendation": issue.recommendation,
                    "auto_fixable": issue.auto_fixable
                })
        
        # Check for cost conflicts
        if architect_proposal.estimated_monthly_cost:
            cost_issues = [i for i in critic_review.issues if i.category == "cost"]
            if cost_issues:
                conflicts.append({
                    "type": "cost_conflict",
                    "architect_estimate": architect_proposal.estimated_monthly_cost,
                    "critic_concerns": [i.description for i in cost_issues],
                    "potential_savings": "See critic recommendations"
                })
        
        # Check for compliance conflicts
        required_compliance = set(architect_proposal.compliance_frameworks)
        compliance_issues = [i for i in critic_review.issues if i.category == "compliance"]
        if compliance_issues:
            conflicts.append({
                "type": "compliance_conflict",
                "required_frameworks": list(required_compliance),
                "violations": [i.description for i in compliance_issues]
            })
        
        return conflicts
    
    def _generate_final_recommendation(
        self,
        architect_proposal: ArchitectProposal,
        critic_review: CriticReview,
        conflicts: List[Dict[str, Any]]
    ) -> str:
        """Generate final recommendation based on both agent outputs."""
        
        if critic_review.overall_score >= 90:
            return f"""✅ **APPROVED** - Architecture meets high standards (Score: {critic_review.overall_score}/100)

The Architect's proposal is well-designed with only minor improvements needed.

**Strengths:**
{chr(10).join(f"• {s}" for s in critic_review.strengths)}

**Minor Issues:** {len(critic_review.issues)} issues found (review details for optimization opportunities)
"""
        
        elif critic_review.overall_score >= 70:
            critical_count = len([i for i in critic_review.issues if i.severity == "critical"])
            high_count = len([i for i in critic_review.issues if i.severity == "high"])
            
            return f"""⚠️  **APPROVE WITH CHANGES** - Architecture is sound but requires fixes (Score: {critic_review.overall_score}/100)

The core design is solid, but address these issues before deployment:

**Critical Issues:** {critical_count}
**High Priority Issues:** {high_count}
**Total Issues:** {len(critic_review.issues)}

**Strengths:**
{chr(10).join(f"• {s}" for s in critic_review.strengths[:3])}

**Required Actions:**
{chr(10).join(f"• {i.title}: {i.recommendation}" for i in critic_review.issues if i.severity in ["critical", "high"])}

{"**Auto-Fix Available:** Use the 'Fix It' button to automatically resolve " + str(len([i for i in critic_review.issues if i.auto_fixable])) + " issues" if any(i.auto_fixable for i in critic_review.issues) else ""}
"""
        
        else:
            critical_count = len([i for i in critic_review.issues if i.severity == "critical"])
            
            return f"""❌ **REJECT** - Architecture has significant issues (Score: {critic_review.overall_score}/100)

The proposed architecture requires major revisions before deployment.

**Critical Issues:** {critical_count}
**Total Issues:** {len(critic_review.issues)}

**Major Concerns:**
{chr(10).join(f"• [{i.category.upper()}] {i.title}" for i in critic_review.issues if i.severity == "critical")}

**Recommendation:** Address all critical issues and re-run validation.

{critic_review.summary}
"""


async def create_dual_pass_validator(agent_client) -> DualPassValidator:
    """
    Factory function to create and initialize a DualPassValidator.
    
    Args:
        agent_client: Azure AI or OpenAI chat client
        
    Returns:
        Initialized DualPassValidator instance
    """
    validator = DualPassValidator(agent_client)
    await validator.initialize()
    return validator
