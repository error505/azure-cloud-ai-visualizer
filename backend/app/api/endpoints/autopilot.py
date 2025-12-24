"""
Full Autopilot API Endpoints

Provides the "magic button" experience:
- POST /api/autopilot/parse - Parse natural language requirements
- POST /api/autopilot/generate - Generate complete architecture from requirements
- GET /api/autopilot/status/{run_id} - Check generation status
"""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.deps import get_agent_client
from app.agents.autopilot_engine import create_autopilot_engine, ParsedRequirements
from dataclasses import asdict

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autopilot", tags=["autopilot"])


class ParseRequirementsRequest(BaseModel):
    """Request to parse natural language requirements."""
    requirements: str = Field(..., description="Natural language architecture requirements")


class GenerateArchitectureRequest(BaseModel):
    """Request to generate complete architecture."""
    requirements: str = Field(..., description="Natural language requirements")
    use_parallel_pass: bool = Field(default=True, description="Use parallel agent review for faster, more thorough generation")


class AutopilotResponse(BaseModel):
    """Response from autopilot operations."""
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/parse", response_model=AutopilotResponse)
async def parse_requirements(
    request: ParseRequirementsRequest,
    agent_client=Depends(get_agent_client)
):
    """
    Parse natural language requirements into structured format.
    
    Extracts:
    - Workload type (e-commerce, ML, analytics, etc.)
    - Required Azure services
    - Compliance frameworks
    - Budget constraints
    - Performance/scale/data requirements
    - External integrations
    
    Returns structured requirements for review before generation.
    """
    try:
        logger.info(f"Parsing requirements: {request.requirements[:100]}...")
        
        # Create autopilot engine
        engine = await create_autopilot_engine(agent_client)
        
        # Parse requirements
        parsed: ParsedRequirements = await engine.parse_requirements(request.requirements)
        
        # Convert to dict for JSON response
        result = asdict(parsed)
        
        logger.info(f"Requirements parsed successfully: {parsed.workload_type}")
        
        return AutopilotResponse(
            success=True,
            result=result
        )
        
    except Exception as e:
        logger.error(f"Requirements parsing failed: {e}")
        return AutopilotResponse(
            success=False,
            error=str(e)
        )


@router.post("/generate", response_model=AutopilotResponse)
async def generate_architecture(
    request: GenerateArchitectureRequest,
    agent_client=Depends(get_agent_client)
):
    """
    Generate complete production-ready architecture from natural language requirements.
    
    This is the "magic button" that:
    1. Parses requirements
    2. Orchestrates multi-agent team (Landing Zone + Security + Cost + Reliability + Network)
    3. Generates complete diagram with 20-40+ services
    4. Creates Bicep and Terraform IaC
    5. Estimates costs
    6. Validates compliance
    
    Returns:
    - Complete ReactFlow diagram
    - Architecture description
    - IaC code (Bicep + Terraform)
    - Cost estimates
    - Compliance validation
    - Run ID for tracking
    """
    try:
        logger.info("Starting full architecture generation...")
        
        # Create autopilot engine
        engine = await create_autopilot_engine(agent_client)
        
        # Parse requirements first
        parsed_requirements = await engine.parse_requirements(request.requirements)
        
        logger.info(f"Generating architecture for {parsed_requirements.workload_type} workload...")
        
        # Generate complete architecture
        architecture = await engine.generate_complete_architecture(
            requirements=parsed_requirements,
            use_parallel_pass=request.use_parallel_pass
        )
        
        logger.info(f"Architecture generation complete! Services: {architecture['services_count']}, Run ID: {architecture['run_id']}")
        
        return AutopilotResponse(
            success=True,
            result=architecture
        )
        
    except Exception as e:
        logger.error(f"Architecture generation failed: {e}")
        import traceback
        traceback.print_exc()
        return AutopilotResponse(
            success=False,
            error=str(e)
        )


@router.get("/health")
async def health_check():
    """Health check endpoint for autopilot service."""
    return {"status": "healthy", "service": "full-autopilot"}
