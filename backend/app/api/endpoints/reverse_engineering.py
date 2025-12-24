"""
Reverse Engineering API Endpoints

Endpoints:
- POST /api/reverse/import - Import cloud inventory JSON into InfraGraph
- POST /api/reverse/detect - Auto-detect provider from inventory
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.cloud_parsers import normalize_azure, normalize_aws, normalize_gcp, detect_provider, parse_inventory
from app.models.infra_models import (
    CloudProvider,
    InfraGraph,
    InfraNode,
    InfraEdge,
    ReverseEngineeringResult,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# -----------------------------------------------------------------------------
# Request/Response Models
# -----------------------------------------------------------------------------

class ReverseImportRequest(BaseModel):
    """Request to import cloud inventory."""
    project_id: str = Field(..., description="Project ID to associate with import")
    provider: Optional[str] = Field(None, description="Cloud provider (azure/aws/gcp) - auto-detects if not provided")
    inventory: Dict[str, Any] = Field(..., description="Raw cloud inventory JSON")


class DetectProviderRequest(BaseModel):
    """Request to detect provider from inventory."""
    inventory: Dict[str, Any] = Field(..., description="Raw cloud inventory JSON")


class DetectProviderResponse(BaseModel):
    """Response for provider detection."""
    provider: Optional[str] = Field(None, description="Detected provider or null")
    confidence: str = Field(..., description="Detection confidence (high/medium/low)")
    hints: List[str] = Field(default_factory=list, description="Detection hints")


class InfraNodeResponse(BaseModel):
    """Serializable InfraNode for API response."""
    id: str
    provider: str
    service_type: str
    label: str
    resource_id: Optional[str] = None
    resource_type: Optional[str] = None
    parent_id: Optional[str] = None
    region: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)
    properties: Dict[str, Any] = Field(default_factory=dict)
    icon_path: Optional[str] = None
    category: Optional[str] = None


class InfraEdgeResponse(BaseModel):
    """Serializable InfraEdge for API response."""
    id: Optional[str] = None
    source: str
    target: str
    edge_type: str
    label: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    source_handle: Optional[str] = None
    target_handle: Optional[str] = None


class InfraGraphResponse(BaseModel):
    """Serializable InfraGraph for API response."""
    provider: str
    nodes: List[InfraNodeResponse]
    edges: List[InfraEdgeResponse]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source: Optional[str] = None


class ReverseEngineeringResponse(BaseModel):
    """Response for reverse engineering import."""
    success: bool
    graph: InfraGraphResponse
    nodes_imported: int
    edges_inferred: int
    warnings: List[str]
    errors: List[str]
    source_provider: str
    import_timestamp: str


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _graph_to_response(graph: InfraGraph) -> InfraGraphResponse:
    """Convert InfraGraph to API response format."""
    nodes = [
        InfraNodeResponse(
            id=n.id,
            provider=n.provider.value if hasattr(n.provider, 'value') else str(n.provider),
            service_type=n.service_type,
            label=n.label,
            resource_id=n.resource_id,
            resource_type=n.resource_type,
            parent_id=n.parent_id,
            region=n.region,
            tags=n.tags,
            properties=n.properties,
            icon_path=n.icon_path,
            category=n.category,
        )
        for n in graph.nodes
    ]
    
    edges = [
        InfraEdgeResponse(
            id=e.id,
            source=e.source,
            target=e.target,
            edge_type=e.edge_type.value if hasattr(e.edge_type, 'value') else str(e.edge_type),
            label=e.label,
            properties=e.properties,
            source_handle=e.source_handle,
            target_handle=e.target_handle,
        )
        for e in graph.edges
    ]
    
    return InfraGraphResponse(
        provider=graph.provider.value if hasattr(graph.provider, 'value') else str(graph.provider),
        nodes=nodes,
        edges=edges,
        metadata=graph.metadata,
        source=graph.source,
    )


def _result_to_response(result: ReverseEngineeringResult) -> ReverseEngineeringResponse:
    """Convert ReverseEngineeringResult to API response."""
    return ReverseEngineeringResponse(
        success=result.success,
        graph=_graph_to_response(result.graph),
        nodes_imported=result.nodes_imported,
        edges_inferred=result.edges_inferred,
        warnings=result.warnings,
        errors=result.errors,
        source_provider=result.source_provider.value if hasattr(result.source_provider, 'value') else str(result.source_provider),
        import_timestamp=result.import_timestamp.isoformat(),
    )


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("/reverse/import", response_model=ReverseEngineeringResponse)
async def reverse_import(request: ReverseImportRequest):
    """
    Import cloud inventory JSON and convert to InfraGraph.
    
    Supports:
    - Azure Resource Graph exports
    - AWS CloudFormation/Config exports
    - GCP Cloud Asset Inventory exports
    
    Auto-detects provider if not specified.
    """
    try:
        logger.info(f"Reverse engineering import for project {request.project_id}")
        
        warnings: List[str] = []
        errors: List[str] = []
        
        # Determine provider
        provider: Optional[CloudProvider] = None
        if request.provider:
            try:
                provider = CloudProvider(request.provider.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid provider: {request.provider}. Must be azure, aws, or gcp."
                )
        else:
            detected = detect_provider(request.inventory)
            if detected:
                provider = detected
                warnings.append(f"Auto-detected provider: {provider.value}")
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Could not auto-detect cloud provider. Please specify provider explicitly."
                )
        
        # Parse inventory
        try:
            graph = parse_inventory(request.inventory, provider)
        except Exception as e:
            logger.error(f"Failed to parse inventory: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to parse inventory: {str(e)}"
            )
        
        # Build result
        result = ReverseEngineeringResult(
            success=True,
            graph=graph,
            nodes_imported=len(graph.nodes),
            edges_inferred=len(graph.edges),
            warnings=warnings,
            errors=errors,
            source_provider=provider,
            import_timestamp=datetime.utcnow(),
        )
        
        logger.info(
            f"Import complete: {result.nodes_imported} nodes, "
            f"{result.edges_inferred} edges for {provider.value}"
        )
        
        return _result_to_response(result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in reverse engineering import: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")


@router.post("/reverse/detect", response_model=DetectProviderResponse)
async def detect_provider_endpoint(request: DetectProviderRequest):
    """
    Auto-detect cloud provider from inventory JSON structure.
    
    Returns the detected provider and confidence level.
    """
    try:
        logger.info("Detecting provider from inventory")
        
        hints: List[str] = []
        
        # Attempt detection
        provider = detect_provider(request.inventory)
        
        if provider:
            # Gather hints about detection
            if "value" in request.inventory:
                hints.append("Found Azure Resource Graph 'value' array")
            if "Resources" in request.inventory:
                hints.append("Found CloudFormation 'Resources' object")
            if "assets" in request.inventory:
                hints.append("Found GCP Cloud Asset 'assets' array")
            if "resources" in request.inventory:
                first = request.inventory["resources"][0] if request.inventory["resources"] else {}
                if "type" in first and first["type"].lower().startswith("microsoft."):
                    hints.append("Found Azure resource type pattern")
                elif "assetType" in first:
                    hints.append("Found GCP assetType pattern")
            
            confidence = "high" if len(hints) > 0 else "medium"
            
            return DetectProviderResponse(
                provider=provider.value,
                confidence=confidence,
                hints=hints,
            )
        else:
            return DetectProviderResponse(
                provider=None,
                confidence="low",
                hints=["Could not determine provider from inventory structure"],
            )
            
    except Exception as e:
        logger.error(f"Error detecting provider: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Detection failed: {str(e)}")


@router.get("/reverse/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "reverse-engineering"}
