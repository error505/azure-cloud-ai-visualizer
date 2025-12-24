"""
Compliance Autopilot API Endpoints

Endpoints:
- POST /api/compliance/validate - Validate diagram compliance
- POST /api/compliance/detect - Auto-detect required frameworks
- GET /api/compliance/frameworks - List available frameworks
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agents.compliance_engine import (
    create_compliance_engine,
    ComplianceEngine,
    ComplianceReport,
    ComplianceViolation
)
from app.deps import get_agent_client

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class ValidateComplianceRequest(BaseModel):
    """Request to validate compliance."""
    diagram: Dict[str, Any] = Field(..., description="ReactFlow diagram to validate")
    frameworks: Optional[List[str]] = Field(None, description="Frameworks to check (auto-detects if None)")


class DetectFrameworksRequest(BaseModel):
    """Request to detect required frameworks."""
    diagram: Dict[str, Any] = Field(..., description="ReactFlow diagram to analyze")


class ComplianceViolationResponse(BaseModel):
    """Compliance violation response."""
    framework: str
    requirement_id: str
    title: str
    description: str
    affected_services: List[str]
    severity: str
    remediation: str
    auto_fixable: bool


class ComplianceReportResponse(BaseModel):
    """Compliance report response."""
    frameworks: List[str]
    overall_score: int
    violations: List[ComplianceViolationResponse]
    compliant_controls: List[str]
    recommendations: List[str]
    generated_at: str
    services_analyzed: int


class DetectFrameworksResponse(BaseModel):
    """Response for framework detection."""
    required_frameworks: List[str]
    rationale: Dict[str, str]


class FrameworkInfo(BaseModel):
    """Information about a compliance framework."""
    name: str
    description: str
    requirements_count: int


class ListFrameworksResponse(BaseModel):
    """Response listing available frameworks."""
    frameworks: List[FrameworkInfo]


@router.post("/compliance/validate", response_model=ComplianceReportResponse)
async def validate_compliance(
    request: ValidateComplianceRequest,
    agent_client=Depends(get_agent_client)
):
    """
    Validate diagram against compliance frameworks.
    
    Auto-detects required frameworks if not specified.
    Returns compliance score, violations, and recommendations.
    """
    try:
        logger.info(f"Validating compliance for {len(request.frameworks or [])} frameworks")
        
        # Create compliance engine
        engine = create_compliance_engine(agent_client)
        
        # Validate
        report: ComplianceReport = engine.validate_compliance(
            diagram=request.diagram,
            frameworks=request.frameworks
        )
        
        # Convert to response
        violations = [
            ComplianceViolationResponse(
                framework=v.framework,
                requirement_id=v.requirement_id,
                title=v.title,
                description=v.description,
                affected_services=v.affected_services,
                severity=v.severity,
                remediation=v.remediation,
                auto_fixable=v.auto_fixable
            )
            for v in report.violations
        ]
        
        response = ComplianceReportResponse(
            frameworks=report.frameworks,
            overall_score=report.overall_score,
            violations=violations,
            compliant_controls=report.compliant_controls,
            recommendations=report.recommendations,
            generated_at=report.generated_at,
            services_analyzed=report.services_analyzed
        )
        
        logger.info(f"Compliance validation complete: {report.overall_score}/100")
        
        return response
    
    except Exception as e:
        logger.error(f"Error validating compliance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Compliance validation failed: {str(e)}")


@router.post("/compliance/detect", response_model=DetectFrameworksResponse)
async def detect_frameworks(
    request: DetectFrameworksRequest,
    agent_client=Depends(get_agent_client)
):
    """
    Auto-detect required compliance frameworks from diagram.
    
    Analyzes diagram for healthcare, payment, EU data indicators.
    """
    try:
        logger.info("Detecting required compliance frameworks")
        
        # Create compliance engine
        engine = create_compliance_engine(agent_client)
        
        # Detect
        frameworks = engine.detect_required_compliance(request.diagram)
        
        # Build rationale
        rationale = {}
        if "HIPAA" in frameworks:
            rationale["HIPAA"] = "Healthcare/PHI data detected in architecture"
        if "PCI-DSS" in frameworks:
            rationale["PCI-DSS"] = "Payment processing detected in architecture"
        if "GDPR" in frameworks:
            rationale["GDPR"] = "EU data or privacy requirements detected"
        if "ISO 27001" in frameworks:
            rationale["ISO 27001"] = "General information security framework"
        if "SOC 2" in frameworks:
            rationale["SOC 2"] = "Service organization controls for cloud services"
        
        response = DetectFrameworksResponse(
            required_frameworks=frameworks,
            rationale=rationale
        )
        
        logger.info(f"Detected {len(frameworks)} required frameworks")
        
        return response
    
    except Exception as e:
        logger.error(f"Error detecting frameworks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Framework detection failed: {str(e)}")


@router.get("/compliance/frameworks", response_model=ListFrameworksResponse)
async def list_frameworks():
    """
    List all available compliance frameworks.
    
    Returns framework names, descriptions, and requirement counts.
    """
    try:
        from app.agents.compliance_engine import COMPLIANCE_FRAMEWORKS
        
        frameworks = [
            FrameworkInfo(
                name="ISO 27001",
                description="International standard for information security management",
                requirements_count=len(COMPLIANCE_FRAMEWORKS.get("ISO 27001", {}))
            ),
            FrameworkInfo(
                name="SOC 2",
                description="Service organization controls for SaaS providers",
                requirements_count=len(COMPLIANCE_FRAMEWORKS.get("SOC 2", {}))
            ),
            FrameworkInfo(
                name="HIPAA",
                description="Healthcare data protection and privacy",
                requirements_count=len(COMPLIANCE_FRAMEWORKS.get("HIPAA", {}))
            ),
            FrameworkInfo(
                name="PCI-DSS",
                description="Payment card industry data security standard",
                requirements_count=len(COMPLIANCE_FRAMEWORKS.get("PCI-DSS", {}))
            ),
            FrameworkInfo(
                name="GDPR",
                description="EU General Data Protection Regulation",
                requirements_count=len(COMPLIANCE_FRAMEWORKS.get("GDPR", {}))
            )
        ]
        
        return ListFrameworksResponse(frameworks=frameworks)
    
    except Exception as e:
        logger.error(f"Error listing frameworks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list frameworks: {str(e)}")


@router.get("/compliance/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "compliance"}
