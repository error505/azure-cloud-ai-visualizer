"""
Dual-Pass Validation API Endpoint

Provides endpoints for:
- Validating architecture requirements (new designs)
- Validating existing diagrams (audits)
- Retrieving validation results
"""

import logging
from typing import Any, Dict, Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.deps import get_agent_client
from app.agents.dual_pass_validation import create_dual_pass_validator, DualPassResult
from app.agents.auto_remediation import AutoRemediationEngine
from dataclasses import asdict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/validation", tags=["validation"])


class ValidateRequirementsRequest(BaseModel):
    """Request to validate architecture requirements."""
    requirements: str = Field(..., description="Natural language requirements")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context (budget, compliance, etc)")


class ValidateExistingDiagramRequest(BaseModel):
    """Request to validate an existing diagram."""
    diagram: Dict[str, Any] = Field(..., description="ReactFlow diagram with nodes/edges/groups")
    requirements: Optional[str] = Field(None, description="Original requirements if available")


class ValidationResponse(BaseModel):
    """Response containing validation results."""
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/requirements", response_model=ValidationResponse)
async def validate_requirements(
    request: ValidateRequirementsRequest,
    agent_client=Depends(get_agent_client)
):
    """
    Validate architecture requirements through dual-pass process.
    
    Returns:
    - Architect's proposed design
    - Critic's review with issues
    - Conflicts between the two
    - Final recommendation
    - Auto-fix availability
    """
    try:
        logger.info(f"Validating requirements: {request.requirements[:100]}...")
        
        # Create validator
        validator = await create_dual_pass_validator(agent_client)
        
        # Run dual-pass validation
        result: DualPassResult = await validator.validate_requirements(
            requirements=request.requirements,
            context=request.context
        )
        
        # Convert dataclasses to dicts for JSON serialization
        response_data = {
            "architect_proposal": {
                "diagram": result.architect_proposal.diagram,
                "rationale": result.architect_proposal.rationale,
                "services_count": result.architect_proposal.services_count,
                "estimated_monthly_cost": result.architect_proposal.estimated_monthly_cost,
                "compliance_frameworks": result.architect_proposal.compliance_frameworks
            },
            "critic_review": {
                "overall_score": result.critic_review.overall_score,
                "issues": [asdict(issue) for issue in result.critic_review.issues],
                "strengths": result.critic_review.strengths,
                "summary": result.critic_review.summary,
                "recommended_changes": result.critic_review.recommended_changes
            },
            "conflicts": result.conflicts,
            "final_recommendation": result.final_recommendation,
            "auto_fix_available": result.auto_fix_available
        }
        
        logger.info(f"Validation completed. Score: {result.critic_review.overall_score}/100, Issues: {len(result.critic_review.issues)}")
        
        return ValidationResponse(
            success=True,
            result=response_data
        )
        
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return ValidationResponse(
            success=False,
            error=str(e)
        )


@router.post("/diagram", response_model=ValidationResponse)
async def validate_existing_diagram(
    request: ValidateExistingDiagramRequest,
    agent_client=Depends(get_agent_client)
):
    """
    Validate an existing diagram through dual-pass process.
    
    Returns:
    - Architect's review/improvements
    - Critic's audit findings
    - Conflicts and issues
    - Final recommendation
    - Auto-fix availability
    """
    try:
        nodes_count = len(request.diagram.get("nodes", []))
        logger.info(f"Validating existing diagram with {nodes_count} nodes...")
        
        # Create validator
        validator = await create_dual_pass_validator(agent_client)
        
        # Run dual-pass validation
        result: DualPassResult = await validator.validate_existing_diagram(
            diagram=request.diagram,
            requirements=request.requirements
        )
        
        # Convert dataclasses to dicts
        response_data = {
            "architect_proposal": {
                "diagram": result.architect_proposal.diagram,
                "rationale": result.architect_proposal.rationale,
                "services_count": result.architect_proposal.services_count,
                "estimated_monthly_cost": result.architect_proposal.estimated_monthly_cost,
                "compliance_frameworks": result.architect_proposal.compliance_frameworks
            },
            "critic_review": {
                "overall_score": result.critic_review.overall_score,
                "issues": [asdict(issue) for issue in result.critic_review.issues],
                "strengths": result.critic_review.strengths,
                "summary": result.critic_review.summary,
                "recommended_changes": result.critic_review.recommended_changes
            },
            "conflicts": result.conflicts,
            "final_recommendation": result.final_recommendation,
            "auto_fix_available": result.auto_fix_available
        }
        
        critical_issues = len([i for i in result.critic_review.issues if i.severity == "critical"])
        logger.info(f"Diagram validation completed. Score: {result.critic_review.overall_score}/100, Critical Issues: {critical_issues}")
        
        return ValidationResponse(
            success=True,
            result=response_data
        )
        
    except Exception as e:
        logger.error(f"Diagram validation failed: {e}")
        return ValidationResponse(
            success=False,
            error=str(e)
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for validation service."""
    return {"status": "healthy", "service": "dual-pass-validation"}


class ApplyFixesRequest(BaseModel):
    """Request to apply auto-remediation fixes."""
    diagram: Dict[str, Any] = Field(..., description="Current diagram")
    issues: List[Dict[str, Any]] = Field(..., description="Issues to fix")


@router.post("/apply-fixes", response_model=ValidationResponse)
async def apply_auto_fixes(request: ApplyFixesRequest):
    """
    Apply automatic remediation fixes to diagram.
    
    Takes validation issues and automatically fixes them by:
    - Adding security components (NSGs, Key Vault, Private Endpoints)
    - Optimizing costs (right-sizing, autoscaling, reservations)
    - Improving reliability (backups, redundancy, health probes)
    - Enabling compliance (logging, diagnostic settings, tags)
    - Enhancing performance (caching, monitoring)
    
    Returns the updated diagram with all fixes applied.
    """
    try:
        logger.info(f"Applying auto-fixes for {len(request.issues)} issues...")
        
        # Create remediation engine
        engine = AutoRemediationEngine()
        
        # Apply fixes
        updated_diagram = engine.remediate_issues(
            diagram=request.diagram,
            issues=request.issues
        )
        
        # Count changes
        original_nodes = len(request.diagram.get('nodes', []))
        updated_nodes = len(updated_diagram.get('nodes', []))
        nodes_added = updated_nodes - original_nodes
        
        logger.info(f"Auto-fix completed. Added {nodes_added} nodes, modified existing resources")
        
        return ValidationResponse(
            success=True,
            result={
                'diagram': updated_diagram,
                'changes': {
                    'nodes_added': nodes_added,
                    'issues_fixed': len(request.issues),
                    'summary': f'Applied {len(request.issues)} automatic fixes'
                }
            }
        )
        
    except Exception as e:
        logger.error(f"Auto-fix failed: {e}")
        return ValidationResponse(
            success=False,
            error=str(e)
        )
