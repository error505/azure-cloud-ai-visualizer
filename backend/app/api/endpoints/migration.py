"""
Migration API Endpoints

Endpoints:
- POST /api/migration/plan - Generate migration plan from source to Azure
- POST /api/migration/ai-plan - AI-powered migration planning with Agent Framework
- POST /api/migration/ai-stream - Stream AI migration analysis
- GET /api/migration/mappings - Get available service mappings
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.models.infra_models import (
    CloudProvider,
    InfraGraph,
    InfraNode,
    InfraEdge,
    MigrationResult,
    MigrationMapping,
    Severity,
)
from app.iac_generators.aws_migration import migrate_aws_diagram, AWS_TO_AZURE_SERVICE_CATALOG
from app.iac_generators.gcp_migration import migrate_gcp_diagram, GCP_TO_AZURE_MAPPINGS
from app.deps import get_agent_client
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter()


# -----------------------------------------------------------------------------
# Request/Response Models
# -----------------------------------------------------------------------------

class MigrationPlanRequest(BaseModel):
    """Request to generate migration plan."""
    project_id: str = Field(..., description="Project ID")
    source_provider: str = Field(..., description="Source cloud provider (aws/gcp)")
    target_provider: str = Field("azure", description="Target provider (always azure for now)")
    diagram: Dict[str, Any] = Field(..., description="Source diagram with nodes and edges")
    options: Optional[Dict[str, Any]] = Field(None, description="Migration options")


class ServiceMappingResponse(BaseModel):
    """Response for a single service mapping."""
    source_service: str
    source_aliases: List[str]
    target_service: str
    target_resource_type: str
    category: str
    description: str
    aws_monthly_cost: Optional[float] = None
    azure_monthly_cost: Optional[float] = None
    cost_assumptions: Optional[str] = None


class MigrationMappingsResponse(BaseModel):
    """Response for available service mappings."""
    aws_mappings: List[ServiceMappingResponse]
    gcp_mappings: List[ServiceMappingResponse]
    total_aws: int
    total_gcp: int


class MigrationNodeResponse(BaseModel):
    """Migrated node in response."""
    id: str
    provider: str
    service_type: str
    label: str
    resource_type: Optional[str] = None
    category: Optional[str] = None
    parent_id: Optional[str] = None
    region: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    properties: Dict[str, Any] = Field(default_factory=dict)


class MigrationEdgeResponse(BaseModel):
    """Migrated edge in response."""
    id: Optional[str] = None
    source: str
    target: str
    edge_type: str = "dependency"
    label: Optional[str] = None


class MigrationMappingResponse(BaseModel):
    """Individual mapping in response."""
    source_node_id: str
    source_service: str
    target_service: str
    target_resource_type: str
    source_monthly_cost: Optional[float] = None
    target_monthly_cost: Optional[float] = None
    cost_delta: Optional[float] = None
    migration_complexity: str = "medium"
    migration_notes: Optional[str] = None
    risks: List[str] = Field(default_factory=list)


class MigrationPlanResponse(BaseModel):
    """Response for migration plan."""
    success: bool
    source_provider: str
    target_provider: str
    
    # Graphs
    source_nodes: List[MigrationNodeResponse]
    source_edges: List[MigrationEdgeResponse]
    target_nodes: List[MigrationNodeResponse]
    target_edges: List[MigrationEdgeResponse]
    
    # Mappings
    mappings: List[MigrationMappingResponse]
    
    # Cost summary
    source_monthly_total: float
    target_monthly_total: float
    total_savings: float
    savings_percent: Optional[float] = None
    cost_summary_markdown: Optional[str] = None
    
    # Assessment
    overall_complexity: str = "medium"
    estimated_duration_days: Optional[int] = None
    key_risks: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    
    # Unmapped
    unmapped_services: List[Dict[str, Any]] = Field(default_factory=list)
    
    # IaC
    bicep_snippets: List[Dict[str, Any]] = Field(default_factory=list)
    
    created_at: str


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _convert_aws_result_to_response(result) -> MigrationPlanResponse:
    """Convert AwsMigrationResult to API response."""
    diagram = result.diagram
    nodes = diagram.get("nodes", [])
    edges = diagram.get("edges", [])
    
    # Build source and target nodes
    source_nodes = []
    target_nodes = []
    mappings = []
    
    for node in nodes:
        data = node.get("data", {})
        aws_original = data.get("awsOriginal", {})
        
        if aws_original:
            # This node was migrated
            source_nodes.append(MigrationNodeResponse(
                id=node.get("id", ""),
                provider="aws",
                service_type=aws_original.get("title", ""),
                label=aws_original.get("title", ""),
                category=aws_original.get("category", ""),
            ))
            target_nodes.append(MigrationNodeResponse(
                id=node.get("id", ""),
                provider="azure",
                service_type=data.get("title", ""),
                label=data.get("title", ""),
                resource_type=data.get("resourceType"),
                category=data.get("category"),
            ))
        else:
            # Original node
            target_nodes.append(MigrationNodeResponse(
                id=node.get("id", ""),
                provider=data.get("provider", "azure"),
                service_type=data.get("title", ""),
                label=data.get("label", data.get("title", "")),
                category=data.get("category"),
            ))
    
    # Build mappings from converted_nodes
    for conv in result.converted_nodes:
        mappings.append(MigrationMappingResponse(
            source_node_id=conv.get("node_id", ""),
            source_service=conv.get("aws_service", ""),
            target_service=conv.get("azure_service", ""),
            target_resource_type=conv.get("resource_type", ""),
            migration_notes=conv.get("description"),
        ))
    
    # Add cost info from price_summary
    for price in result.price_summary:
        for mapping in mappings:
            if mapping.source_node_id == price.get("node_id"):
                mapping.source_monthly_cost = price.get("aws_monthly")
                mapping.target_monthly_cost = price.get("azure_monthly")
                mapping.cost_delta = price.get("delta")
    
    # Build edges
    target_edges = [
        MigrationEdgeResponse(
            id=e.get("id"),
            source=e.get("source", ""),
            target=e.get("target", ""),
            label=e.get("label"),
        )
        for e in edges
    ]
    
    # Cost summary
    cost_summary = result.cost_summary or {}
    
    return MigrationPlanResponse(
        success=result.applied,
        source_provider="aws",
        target_provider="azure",
        source_nodes=source_nodes,
        source_edges=[],
        target_nodes=target_nodes,
        target_edges=target_edges,
        mappings=mappings,
        source_monthly_total=cost_summary.get("aws_monthly_total", 0),
        target_monthly_total=cost_summary.get("azure_monthly_total", 0),
        total_savings=cost_summary.get("savings", 0),
        savings_percent=cost_summary.get("savings_percent"),
        cost_summary_markdown=cost_summary.get("summary_markdown"),
        overall_complexity="medium",
        key_risks=[],
        recommendations=[
            "Review service mappings before migration",
            "Test workloads in Azure staging environment",
            "Plan for data migration strategy",
        ],
        unmapped_services=result.unmapped_services,
        bicep_snippets=result.bicep_snippets,
        created_at=datetime.utcnow().isoformat(),
    )


def _convert_gcp_result_to_response(result) -> MigrationPlanResponse:
    """Convert GcpMigrationResult to API response."""
    diagram = result.diagram
    nodes = diagram.get("nodes", [])
    edges = diagram.get("edges", [])
    
    source_nodes = []
    target_nodes = []
    mappings = []
    
    for node in nodes:
        data = node.get("data", {})
        gcp_original = data.get("gcpOriginal", {})
        
        if gcp_original:
            source_nodes.append(MigrationNodeResponse(
                id=node.get("id", ""),
                provider="gcp",
                service_type=gcp_original.get("title", ""),
                label=gcp_original.get("title", ""),
                category=gcp_original.get("category", ""),
            ))
            target_nodes.append(MigrationNodeResponse(
                id=node.get("id", ""),
                provider="azure",
                service_type=data.get("title", ""),
                label=data.get("title", ""),
                resource_type=data.get("resourceType"),
                category=data.get("category"),
            ))
        else:
            target_nodes.append(MigrationNodeResponse(
                id=node.get("id", ""),
                provider=data.get("provider", "azure"),
                service_type=data.get("title", ""),
                label=data.get("label", data.get("title", "")),
                category=data.get("category"),
            ))
    
    for conv in getattr(result, 'converted_nodes', []):
        mappings.append(MigrationMappingResponse(
            source_node_id=conv.get("node_id", ""),
            source_service=conv.get("gcp_service", ""),
            target_service=conv.get("azure_service", ""),
            target_resource_type=conv.get("resource_type", ""),
            migration_notes=conv.get("description"),
        ))
    
    for price in getattr(result, 'price_summary', []):
        for mapping in mappings:
            if mapping.source_node_id == price.get("node_id"):
                mapping.source_monthly_cost = price.get("gcp_monthly")
                mapping.target_monthly_cost = price.get("azure_monthly")
                mapping.cost_delta = price.get("delta")
    
    target_edges = [
        MigrationEdgeResponse(
            id=e.get("id"),
            source=e.get("source", ""),
            target=e.get("target", ""),
            label=e.get("label"),
        )
        for e in edges
    ]
    
    cost_summary = getattr(result, 'cost_summary', {}) or {}
    
    return MigrationPlanResponse(
        success=result.applied,
        source_provider="gcp",
        target_provider="azure",
        source_nodes=source_nodes,
        source_edges=[],
        target_nodes=target_nodes,
        target_edges=target_edges,
        mappings=mappings,
        source_monthly_total=cost_summary.get("gcp_monthly_total", 0),
        target_monthly_total=cost_summary.get("azure_monthly_total", 0),
        total_savings=cost_summary.get("savings", 0),
        savings_percent=cost_summary.get("savings_percent"),
        cost_summary_markdown=cost_summary.get("summary_markdown"),
        overall_complexity="medium",
        key_risks=[],
        recommendations=[
            "Review service mappings before migration",
            "Test workloads in Azure staging environment",
            "Plan for data migration strategy",
        ],
        unmapped_services=getattr(result, 'unmapped_services', []),
        bicep_snippets=getattr(result, 'bicep_snippets', []),
        created_at=datetime.utcnow().isoformat(),
    )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("/migration/ai-plan")
async def create_ai_migration_plan(request: MigrationPlanRequest):
    """
    Generate an AI-powered migration plan using Microsoft Agent Framework.
    
    Uses AI agents to analyze source infrastructure and recommend
    optimal Azure service mappings with intelligent cost analysis.
    """
    try:
        from app.agents.migration_agent import get_migration_agent
        
        logger.info(f"[AI Migration] Starting AI-powered migration analysis for project {request.project_id}")
        logger.info(f"[AI Migration] Source: {request.source_provider}, Target: {request.target_provider}")
        
        source = request.source_provider.lower()
        
        if source not in ("aws", "gcp"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source provider: {source}. Must be 'aws' or 'gcp'."
            )
        
        # Get the migration agent
        agent = await get_migration_agent()
        
        # Get source nodes from diagram
        source_nodes = request.diagram.get("nodes", [])
        
        logger.info(f"[AI Migration] Analyzing {len(source_nodes)} source nodes with AI agent")
        
        # Run AI-powered migration analysis
        result = await agent.analyze_migration(source_nodes, source)
        
        # Convert AI result to response format
        mappings = result.get("mappings", [])
        summary = result.get("summary", {})
        
        # Build target nodes from AI recommendations
        target_nodes = []
        response_mappings = []
        
        for idx, mapping in enumerate(mappings):
            if mapping.get("azure_service") and mapping.get("azure_service") != "Manual Review Required":
                # Create target node
                target_nodes.append(MigrationNodeResponse(
                    id=f"azure-{mapping.get('source_id', idx)}",
                    provider="azure",
                    service_type=mapping.get("azure_service", ""),
                    label=mapping.get("azure_service", ""),
                    resource_type=mapping.get("azure_resource_type"),
                    category=mapping.get("azure_category"),
                ))
            
            # Create mapping response
            response_mappings.append(MigrationMappingResponse(
                source_node_id=mapping.get("source_id", ""),
                source_service=mapping.get("source_service", ""),
                target_service=mapping.get("azure_service", ""),
                target_resource_type=mapping.get("azure_resource_type", ""),
                source_monthly_cost=mapping.get("source_monthly_cost"),
                target_monthly_cost=mapping.get("azure_monthly_cost"),
                cost_delta=(mapping.get("azure_monthly_cost", 0) - mapping.get("source_monthly_cost", 0)) if mapping.get("source_monthly_cost") else None,
                migration_complexity=mapping.get("complexity", "medium"),
                migration_notes=mapping.get("rationale"),
                risks=mapping.get("considerations", []),
            ))
        
        # Build source nodes response
        source_node_responses = []
        for node in source_nodes:
            data = node.get("data", {})
            source_node_responses.append(MigrationNodeResponse(
                id=node.get("id", ""),
                provider=source,
                service_type=data.get("serviceType", ""),
                label=data.get("label") or data.get("title", ""),
                category=data.get("category"),
            ))
        
        response = MigrationPlanResponse(
            success=True,
            source_provider=source,
            target_provider="azure",
            source_nodes=source_node_responses,
            source_edges=[],
            target_nodes=target_nodes,
            target_edges=[],
            mappings=response_mappings,
            source_monthly_total=summary.get("total_source_cost", 0),
            target_monthly_total=summary.get("total_azure_cost", 0),
            total_savings=summary.get("estimated_savings", 0),
            savings_percent=summary.get("savings_percent"),
            cost_summary_markdown=None,
            overall_complexity=summary.get("overall_complexity", "medium"),
            key_risks=summary.get("key_risks", []),
            recommendations=summary.get("recommendations", []),
            unmapped_services=[],
            bicep_snippets=[],
            created_at=datetime.utcnow().isoformat(),
        )
        
        agent_used = result.get("agent_used", True)
        method = result.get("method", "ai_agent")
        
        logger.info(
            f"[AI Migration] Complete: {len(response_mappings)} mappings, "
            f"savings: ${response.total_savings:.2f}/month (method: {method})"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[AI Migration] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI migration planning failed: {str(e)}")


@router.post("/migration/ai-stream")
async def stream_ai_migration_plan(request: MigrationPlanRequest):
    """
    Stream AI-powered migration analysis for real-time updates.
    
    Returns Server-Sent Events with migration progress and recommendations.
    """
    try:
        from app.agents.migration_agent import get_migration_agent
        
        logger.info(f"[AI Migration Stream] Starting for project {request.project_id}")
        
        source = request.source_provider.lower()
        source_nodes = request.diagram.get("nodes", [])
        
        agent = await get_migration_agent()
        
        async def generate():
            yield f"data: {json.dumps({'type': 'start', 'message': f'Analyzing {len(source_nodes)} {source.upper()} services...'})}\n\n"
            
            try:
                async for chunk in agent.stream_analysis(source_nodes, source):
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                
                yield f"data: {json.dumps({'type': 'complete', 'message': 'Migration analysis complete'})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
        
    except Exception as e:
        logger.error(f"[AI Migration Stream] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/migration/plan", response_model=MigrationPlanResponse)
async def create_migration_plan(request: MigrationPlanRequest):
    """
    Generate a migration plan from source cloud to Azure.
    
    Analyzes the source diagram, maps services to Azure equivalents,
    calculates cost differences, and generates IaC snippets.
    """
    try:
        logger.info(f"Creating migration plan for project {request.project_id}")
        logger.info(f"Source: {request.source_provider}, Target: {request.target_provider}")
        
        source = request.source_provider.lower()
        
        if source not in ("aws", "gcp"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid source provider: {source}. Must be 'aws' or 'gcp'."
            )
        
        if request.target_provider.lower() != "azure":
            raise HTTPException(
                status_code=400,
                detail="Only Azure is supported as target provider currently."
            )
        
        # Run migration
        if source == "aws":
            result = migrate_aws_diagram(request.diagram)
            response = _convert_aws_result_to_response(result)
        else:  # gcp
            result = migrate_gcp_diagram(request.diagram)
            response = _convert_gcp_result_to_response(result)
        
        logger.info(
            f"Migration plan created: {len(response.mappings)} mappings, "
            f"savings: ${response.total_savings:.2f}/month"
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating migration plan: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Migration planning failed: {str(e)}")


@router.get("/migration/mappings", response_model=MigrationMappingsResponse)
async def get_service_mappings():
    """
    Get all available service mappings for AWS and GCP to Azure.
    
    Useful for understanding what migrations are supported.
    """
    try:
        aws_mappings = []
        for entry in AWS_TO_AZURE_SERVICE_CATALOG:
            entry_map = cast(Dict[str, Any], entry)
            cost = entry_map.get("cost", {})
            aws_mappings.append(ServiceMappingResponse(
                source_service=entry_map.get("aws", [""])[0] if entry_map.get("aws") else "",
                source_aliases=entry_map.get("aws", []),
                target_service=entry_map.get("azure_service", ""),
                target_resource_type=entry_map.get("azure_resource_type", ""),
                category=entry_map.get("azure_category", ""),
                description=entry_map.get("description", ""),
                aws_monthly_cost=cost.get("aws_monthly") if isinstance(cost, dict) else None,
                azure_monthly_cost=cost.get("azure_monthly") if isinstance(cost, dict) else None,
                cost_assumptions=cost.get("assumptions") if isinstance(cost, dict) else None,
            ))
        gcp_mappings = []
        for entry in GCP_TO_AZURE_MAPPINGS:
            entry_map = cast(Dict[str, Any], entry)
            cost = entry_map.get("cost", {})
            gcp_aliases = entry_map.get("gcp") or []
            gcp_mappings.append(ServiceMappingResponse(
                source_service=gcp_aliases[0] if gcp_aliases else "",
                source_aliases=gcp_aliases,
                target_service=entry_map.get("azure_service", ""),
                target_resource_type=entry_map.get("azure_resource_type", ""),
                category=entry_map.get("azure_category", ""),
                description=entry_map.get("description", ""),
                aws_monthly_cost=None,
                azure_monthly_cost=cost.get("azure_monthly") if isinstance(cost, dict) else None,
                cost_assumptions=cost.get("assumptions") if isinstance(cost, dict) else None,
            ))

        
        return MigrationMappingsResponse(
            aws_mappings=aws_mappings,
            gcp_mappings=gcp_mappings,
            total_aws=len(aws_mappings),
            total_gcp=len(gcp_mappings),
        )
        
    except Exception as e:
        logger.error(f"Error getting service mappings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get mappings: {str(e)}")


@router.get("/migration/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "migration"}
