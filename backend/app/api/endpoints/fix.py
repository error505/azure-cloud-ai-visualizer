"""Fix/Apply API endpoints for applying patches to diagrams."""

from typing import Any, Literal, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# -----------------------------------------------------------------------------
# Request/Response Models
# -----------------------------------------------------------------------------

class SimplePatch(BaseModel):
    """A simple patch operation for diagram modification."""
    node_id: str = Field(..., description="Target node ID (or new node ID for add)")
    action: Literal["add", "remove", "modify", "connect", "disconnect"] = Field(..., description="Patch action")
    properties: Optional[dict[str, Any]] = Field(None, description="Properties to set/update")


class DiagramData(BaseModel):
    """Diagram data structure."""
    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class ApplyFixRequest(BaseModel):
    """Request body for applying fixes."""
    diagram: DiagramData
    patches: list[SimplePatch]
    project_id: Optional[str] = None
    dry_run: bool = Field(default=False, description="If true, returns preview without modifying")


class PatchResult(BaseModel):
    """Result of applying a single patch."""
    patch_id: str
    success: bool
    message: str
    affected_nodes: list[str] = Field(default_factory=list)


class ApplyFixResponse(BaseModel):
    """Response from applying fixes."""
    success: bool
    diagram: Optional[DiagramData] = None
    patches_applied: int
    patches_failed: int
    results: list[PatchResult]
    message: str


class FixApplier:
    """Applies fix patches to diagrams."""
    
    def apply_patches(
        self,
        diagram: DiagramData,
        patches: list[SimplePatch],
        dry_run: bool = False
    ) -> ApplyFixResponse:
        """Apply a list of patches to a diagram."""
        results: list[PatchResult] = []
        modified_diagram = DiagramData(
            nodes=[node.copy() for node in diagram.nodes],
            edges=[edge.copy() for edge in diagram.edges]
        )
        
        patches_applied = 0
        patches_failed = 0
        
        for patch in patches:
            try:
                result = self._apply_single_patch(modified_diagram, patch, dry_run)
                results.append(result)
                if result.success:
                    patches_applied += 1
                else:
                    patches_failed += 1
            except Exception as e:
                logger.error(f"Error applying patch {patch.node_id}: {e}")
                results.append(PatchResult(
                    patch_id=patch.node_id,
                    success=False,
                    message=str(e),
                    affected_nodes=[patch.node_id]
                ))
                patches_failed += 1
        
        return ApplyFixResponse(
            success=patches_failed == 0,
            diagram=modified_diagram if not dry_run else None,
            patches_applied=patches_applied,
            patches_failed=patches_failed,
            results=results,
            message=f"Applied {patches_applied}/{len(patches)} patches successfully"
        )
    
    def _apply_single_patch(
        self,
        diagram: DiagramData,
        patch: SimplePatch,
        dry_run: bool
    ) -> PatchResult:
        """Apply a single patch to the diagram."""
        action = patch.action
        node_id = patch.node_id
        affected_nodes = [node_id]
        
        if action == "add":
            return self._apply_add_patch(diagram, patch, dry_run, affected_nodes)
        elif action == "remove":
            return self._apply_remove_patch(diagram, patch, dry_run, affected_nodes)
        elif action == "modify":
            return self._apply_modify_patch(diagram, patch, dry_run, affected_nodes)
        elif action == "connect":
            return self._apply_connect_patch(diagram, patch, dry_run, affected_nodes)
        elif action == "disconnect":
            return self._apply_disconnect_patch(diagram, patch, dry_run, affected_nodes)
        else:
            return PatchResult(
                patch_id=node_id,
                success=False,
                message=f"Unknown action: {action}",
                affected_nodes=affected_nodes
            )
    
    def _apply_add_patch(
        self,
        diagram: DiagramData,
        patch: SimplePatch,
        dry_run: bool,
        affected_nodes: list[str]
    ) -> PatchResult:
        """Add a new node to the diagram."""
        # Check if node already exists
        existing = next(
            (n for n in diagram.nodes if n.get("id") == patch.node_id),
            None
        )
        if existing:
            return PatchResult(
                patch_id=patch.node_id,
                success=False,
                message=f"Node {patch.node_id} already exists",
                affected_nodes=affected_nodes
            )
        
        if not dry_run:
            # Create new node from patch properties
            new_node = {
                "id": patch.node_id,
                "type": patch.properties.get("type", "azureService") if patch.properties else "azureService",
                "position": patch.properties.get("position", {"x": 100, "y": 100}) if patch.properties else {"x": 100, "y": 100},
                "data": patch.properties.get("data", {"label": patch.node_id}) if patch.properties else {"label": patch.node_id},
            }
            diagram.nodes.append(new_node)
        
        return PatchResult(
            patch_id=patch.node_id,
            success=True,
            message=f"Added node {patch.node_id}" + (" (dry run)" if dry_run else ""),
            affected_nodes=affected_nodes
        )
    
    def _apply_remove_patch(
        self,
        diagram: DiagramData,
        patch: SimplePatch,
        dry_run: bool,
        affected_nodes: list[str]
    ) -> PatchResult:
        """Remove a node from the diagram."""
        node_idx = next(
            (i for i, n in enumerate(diagram.nodes) if n.get("id") == patch.node_id),
            None
        )
        if node_idx is None:
            return PatchResult(
                patch_id=patch.node_id,
                success=False,
                message=f"Node {patch.node_id} not found",
                affected_nodes=affected_nodes
            )
        
        if not dry_run:
            # Remove node
            diagram.nodes.pop(node_idx)
            
            # Remove connected edges
            diagram.edges = [
                e for e in diagram.edges
                if e.get("source") != patch.node_id and e.get("target") != patch.node_id
            ]
        
        return PatchResult(
            patch_id=patch.node_id,
            success=True,
            message=f"Removed node {patch.node_id}" + (" (dry run)" if dry_run else ""),
            affected_nodes=affected_nodes
        )
    
    def _apply_modify_patch(
        self,
        diagram: DiagramData,
        patch: SimplePatch,
        dry_run: bool,
        affected_nodes: list[str]
    ) -> PatchResult:
        """Modify a node's properties."""
        node = next(
            (n for n in diagram.nodes if n.get("id") == patch.node_id),
            None
        )
        if node is None:
            return PatchResult(
                patch_id=patch.node_id,
                success=False,
                message=f"Node {patch.node_id} not found",
                affected_nodes=affected_nodes
            )
        
        if not dry_run and patch.properties:
            # Apply property modifications
            for key, value in patch.properties.items():
                if key == "data":
                    # Merge data properties
                    if "data" not in node:
                        node["data"] = {}
                    if isinstance(value, dict):
                        node["data"].update(value)
                    else:
                        node["data"] = value
                elif key == "position":
                    node["position"] = value
                elif key == "type":
                    node["type"] = value
                else:
                    node[key] = value
        
        return PatchResult(
            patch_id=patch.node_id,
            success=True,
            message=f"Modified node {patch.node_id}" + (" (dry run)" if dry_run else ""),
            affected_nodes=affected_nodes
        )
    
    def _apply_connect_patch(
        self,
        diagram: DiagramData,
        patch: SimplePatch,
        dry_run: bool,
        affected_nodes: list[str]
    ) -> PatchResult:
        """Add a connection between nodes."""
        if not patch.properties or "target" not in patch.properties:
            return PatchResult(
                patch_id=patch.node_id,
                success=False,
                message="Connect action requires 'target' in properties",
                affected_nodes=affected_nodes
            )
        
        target_id = patch.properties["target"]
        affected_nodes.append(target_id)
        
        # Verify both nodes exist
        source_exists = any(n.get("id") == patch.node_id for n in diagram.nodes)
        target_exists = any(n.get("id") == target_id for n in diagram.nodes)
        
        if not source_exists:
            return PatchResult(
                patch_id=patch.node_id,
                success=False,
                message=f"Source node {patch.node_id} not found",
                affected_nodes=affected_nodes
            )
        if not target_exists:
            return PatchResult(
                patch_id=patch.node_id,
                success=False,
                message=f"Target node {target_id} not found",
                affected_nodes=affected_nodes
            )
        
        # Check if edge already exists
        edge_exists = any(
            e.get("source") == patch.node_id and e.get("target") == target_id
            for e in diagram.edges
        )
        if edge_exists:
            return PatchResult(
                patch_id=patch.node_id,
                success=False,
                message=f"Edge from {patch.node_id} to {target_id} already exists",
                affected_nodes=affected_nodes
            )
        
        if not dry_run:
            new_edge = {
                "id": f"{patch.node_id}-{target_id}",
                "source": patch.node_id,
                "target": target_id,
                "type": patch.properties.get("edge_type", "default"),
            }
            diagram.edges.append(new_edge)
        
        return PatchResult(
            patch_id=patch.node_id,
            success=True,
            message=f"Connected {patch.node_id} to {target_id}" + (" (dry run)" if dry_run else ""),
            affected_nodes=affected_nodes
        )
    
    def _apply_disconnect_patch(
        self,
        diagram: DiagramData,
        patch: SimplePatch,
        dry_run: bool,
        affected_nodes: list[str]
    ) -> PatchResult:
        """Remove a connection between nodes."""
        if not patch.properties or "target" not in patch.properties:
            return PatchResult(
                patch_id=patch.node_id,
                success=False,
                message="Disconnect action requires 'target' in properties",
                affected_nodes=affected_nodes
            )
        
        target_id = patch.properties["target"]
        affected_nodes.append(target_id)
        
        # Find edge
        edge_idx = next(
            (i for i, e in enumerate(diagram.edges)
             if e.get("source") == patch.node_id and e.get("target") == target_id),
            None
        )
        if edge_idx is None:
            return PatchResult(
                patch_id=patch.node_id,
                success=False,
                message=f"Edge from {patch.node_id} to {target_id} not found",
                affected_nodes=affected_nodes
            )
        
        if not dry_run:
            diagram.edges.pop(edge_idx)
        
        return PatchResult(
            patch_id=patch.node_id,
            success=True,
            message=f"Disconnected {patch.node_id} from {target_id}" + (" (dry run)" if dry_run else ""),
            affected_nodes=affected_nodes
        )


# Instantiate applier
fix_applier = FixApplier()


@router.post("/fix/apply", response_model=ApplyFixResponse)
async def apply_fixes(request: ApplyFixRequest):
    """
    Apply fix patches to a diagram.
    
    Supports the following actions:
    - add: Add a new node
    - remove: Remove a node and its connections
    - modify: Modify node properties
    - connect: Add an edge between nodes
    - disconnect: Remove an edge between nodes
    
    Use dry_run=true to preview changes without modifying.
    """
    try:
        result = fix_applier.apply_patches(
            diagram=request.diagram,
            patches=request.patches,
            dry_run=request.dry_run
        )
        return result
    except Exception as e:
        logger.exception("Error applying fixes")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fix/preview", response_model=ApplyFixResponse)
async def preview_fixes(request: ApplyFixRequest):
    """
    Preview fix patches without applying them.
    
    Equivalent to apply_fixes with dry_run=true.
    """
    request.dry_run = True
    return await apply_fixes(request)


@router.get("/fix/actions")
async def get_available_actions():
    """
    Get list of available fix actions and their descriptions.
    """
    return {
        "actions": [
            {
                "name": "add",
                "description": "Add a new node to the diagram",
                "required_properties": ["type", "position", "data"]
            },
            {
                "name": "remove",
                "description": "Remove a node and all its connections",
                "required_properties": []
            },
            {
                "name": "modify",
                "description": "Modify properties of an existing node",
                "required_properties": ["data (partial update)"]
            },
            {
                "name": "connect",
                "description": "Add an edge between two nodes",
                "required_properties": ["target"]
            },
            {
                "name": "disconnect",
                "description": "Remove an edge between two nodes",
                "required_properties": ["target"]
            }
        ]
    }
