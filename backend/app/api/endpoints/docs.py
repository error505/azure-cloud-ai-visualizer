"""
Documentation Generator API Endpoints

Endpoints:
- POST /api/docs/generate - Generate documentation (HLD/LLD/Runbook/Deployment)
- GET /api/docs/types - List available document types
"""

import logging
from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.agents.doc_generator import (
    create_documentation_generator,
    DocumentationGenerator
)
from app.deps import get_agent_client

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class GenerateDocRequest(BaseModel):
    """Request to generate documentation."""
    diagram: Dict[str, Any] = Field(..., description="ReactFlow diagram")
    doc_type: Literal["hld", "lld", "runbook", "deployment"] = Field(..., description="Document type")
    requirements: Optional[str] = Field(None, description="Original requirements for HLD context")
    service_configs: Optional[Dict[str, Any]] = Field(None, description="Service configurations for LLD")
    iac_code: Optional[Dict[str, Any]] = Field(None, description="IaC code for deployment guide")


class DocumentMetadataResponse(BaseModel):
    """Document metadata response."""
    document_type: str
    generated_at: str
    diagram_services_count: int
    version: str


class GenerateDocResponse(BaseModel):
    """Documentation generation response."""
    success: bool
    markdown: str
    metadata: DocumentMetadataResponse
    format: str


class DocumentTypeInfo(BaseModel):
    """Information about a document type."""
    type: str
    name: str
    description: str
    sections: int


class ListDocTypesResponse(BaseModel):
    """Response listing available document types."""
    document_types: List[DocumentTypeInfo]


@router.post("/docs/generate", response_model=GenerateDocResponse)
async def generate_documentation(
    request: GenerateDocRequest,
    agent_client=Depends(get_agent_client)
):
    """
    Generate AI-powered documentation from diagram.
    
    Supports:
    - hld: High-Level Design (executive summary, architecture, components, etc.)
    - lld: Low-Level Design (service specs, network, IAM, monitoring, etc.)
    - runbook: Operational runbook (startup, troubleshooting, incident response, etc.)
    - deployment: Deployment guide (prerequisites, steps, validation, rollback, etc.)
    """
    try:
        logger.info(f"Generating {request.doc_type} documentation")
        
        # Create documentation generator
        generator = await create_documentation_generator(agent_client)
        
        # Generate based on type
        if request.doc_type == "hld":
            result = await generator.generate_hld(
                diagram=request.diagram,
                requirements=request.requirements
            )
        elif request.doc_type == "lld":
            result = await generator.generate_lld(
                diagram=request.diagram,
                service_configs=request.service_configs
            )
        elif request.doc_type == "runbook":
            result = await generator.generate_runbook(
                diagram=request.diagram
            )
        elif request.doc_type == "deployment":
            result = await generator.generate_deployment_guide(
                diagram=request.diagram,
                iac_code=request.iac_code
            )
        else:
            raise HTTPException(status_code=400, detail=f"Invalid doc_type: {request.doc_type}")
        
        # Convert metadata to response (support dict or object-like metadata)
        raw_meta = None
        if isinstance(result, dict):
            raw_meta = result.get('metadata')
        else:
            # result may be a simple object with attributes
            raw_meta = getattr(result, 'metadata', None)

        # Normalize metadata to a dict with safe fallbacks
        metadata: dict = {}
        if isinstance(raw_meta, dict):
            metadata = raw_meta
        elif raw_meta is not None:
            try:
                metadata = {
                    'document_type': getattr(raw_meta, 'document_type', None) or getattr(raw_meta, 'type', None),
                    'generated_at': getattr(raw_meta, 'generated_at', None) or getattr(raw_meta, 'generatedAt', None),
                    'diagram_services_count': getattr(raw_meta, 'diagram_services_count', None) or getattr(raw_meta, 'diagramServicesCount', None),
                    'version': getattr(raw_meta, 'version', None),
                }
            except Exception:
                metadata = {}

        metadata_response = DocumentMetadataResponse(
            document_type=str(metadata.get('document_type') or metadata.get('type') or 'unknown'),
            generated_at=str(metadata.get('generated_at') or metadata.get('generatedAt') or ''),
            diagram_services_count=int(metadata.get('diagram_services_count') or metadata.get('diagramServicesCount') or 0),
            version=str(metadata.get('version') or '')
        )
        
        response = GenerateDocResponse(
            success=True,
            markdown=result['markdown'],
            metadata=metadata_response,
            format=result['format']
        )
        
        logger.info(f"Generated {request.doc_type} documentation successfully")
        
        return response
    
    except Exception as e:
        logger.error(f"Error generating documentation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Documentation generation failed: {str(e)}")


@router.get("/docs/types", response_model=ListDocTypesResponse)
async def list_document_types():
    """
    List all available document types.
    
    Returns type codes, names, descriptions, and section counts.
    """
    try:
        document_types = [
            DocumentTypeInfo(
                type="hld",
                name="High-Level Design",
                description="Executive summary, architecture overview, components, data flows, integrations, tech stack, security, scalability, HA/DR, cost considerations",
                sections=10
            ),
            DocumentTypeInfo(
                type="lld",
                name="Low-Level Design",
                description="Detailed service specifications (SKU, config, dependencies), network architecture, IAM, data architecture, monitoring, backup/DR",
                sections=6
            ),
            DocumentTypeInfo(
                type="runbook",
                name="Operational Runbook",
                description="Startup/shutdown procedures, health checks, troubleshooting guide, incident response, maintenance tasks, scaling procedures, backup/recovery, monitoring/alerts",
                sections=10
            ),
            DocumentTypeInfo(
                type="deployment",
                name="Deployment Guide",
                description="Prerequisites, environment setup, deployment steps (Bicep/Terraform), post-deployment config, validation/testing, rollback procedures, common issues",
                sections=7
            )
        ]
        
        return ListDocTypesResponse(document_types=document_types)
    
    except Exception as e:
        logger.error(f"Error listing document types: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list document types: {str(e)}")


@router.get("/docs/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "documentation"}
