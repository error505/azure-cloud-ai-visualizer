"""
InfraGraph Data Models

Unified multi-cloud infrastructure models for:
- Azure, AWS, GCP inventory representation
- Migration planning and tracking
- Compliance analysis and reporting
- Cost optimization and recommendations
- Fix/patch application

All models use Pydantic for validation and serialization.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------

class CloudProvider(str, Enum):
    """Supported cloud providers."""
    AZURE = "azure"
    AWS = "aws"
    GCP = "gcp"
    MIXED = "mixed"  # Multi-cloud architecture


class EdgeType(str, Enum):
    """Types of connections between infrastructure nodes."""
    NETWORK = "network"  # Network connectivity (VNet peering, VPN, etc.)
    DATA = "data"  # Data flow (storage access, database connections)
    DEPENDENCY = "dependency"  # Service dependency
    IDENTITY = "identity"  # Identity/RBAC relationship
    CONTAINS = "contains"  # Parent-child containment


class FixType(str, Enum):
    """Types of fixes that can be applied."""
    COMPLIANCE = "compliance"  # Compliance violation fix
    COST = "cost"  # Cost optimization fix
    SECURITY = "security"  # Security hardening fix
    PERFORMANCE = "performance"  # Performance optimization fix
    MIGRATION = "migration"  # Migration-related fix


class Severity(str, Enum):
    """Severity levels for violations and recommendations."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# -----------------------------------------------------------------------------
# Core InfraGraph Models
# -----------------------------------------------------------------------------

class InfraNode(BaseModel):
    """
    Represents a single infrastructure resource/service.
    
    This is the universal node format that normalizes resources from
    Azure, AWS, and GCP into a common structure.
    """
    id: str = Field(..., description="Unique identifier for the node")
    provider: CloudProvider = Field(..., description="Cloud provider (azure/aws/gcp)")
    service_type: str = Field(..., description="Normalized service type (e.g., 'virtual_machine', 'storage_account')")
    label: str = Field(..., description="Display label for the node")
    
    # Resource identification
    resource_id: Optional[str] = Field(None, description="Cloud-specific resource ID/ARN")
    resource_type: Optional[str] = Field(None, description="Cloud-specific resource type")
    
    # Hierarchy
    parent_id: Optional[str] = Field(None, description="Parent node ID (for grouping)")
    region: Optional[str] = Field(None, description="Deployment region")
    
    # Metadata
    tags: Dict[str, str] = Field(default_factory=dict, description="Resource tags")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Service-specific properties")
    
    # Visual properties (for diagram rendering)
    icon_path: Optional[str] = Field(None, description="Path to service icon")
    category: Optional[str] = Field(None, description="Service category (compute, storage, network, etc.)")
    
    # Original data preservation
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Original cloud-specific data")

    class Config:
        use_enum_values = True


class InfraEdge(BaseModel):
    """
    Represents a connection/relationship between infrastructure nodes.
    """
    id: Optional[str] = Field(None, description="Unique edge identifier")
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    edge_type: EdgeType = Field(EdgeType.DEPENDENCY, description="Type of connection")
    label: Optional[str] = Field(None, description="Edge label/description")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Edge-specific properties")
    
    # For network edges
    source_handle: Optional[str] = Field(None, description="Source connection point")
    target_handle: Optional[str] = Field(None, description="Target connection point")

    class Config:
        use_enum_values = True


class InfraGraph(BaseModel):
    """
    Unified multi-cloud infrastructure graph.
    
    This is the central data structure that represents any cloud architecture,
    whether single-provider or multi-cloud.
    """
    provider: CloudProvider = Field(..., description="Primary provider or 'mixed' for multi-cloud")
    nodes: List[InfraNode] = Field(default_factory=list, description="Infrastructure nodes")
    edges: List[InfraEdge] = Field(default_factory=list, description="Node connections")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Graph-level metadata")
    source: Optional[str] = Field(None, description="Source of the graph (import, scan, manual)")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    class Config:
        use_enum_values = True

    def get_node(self, node_id: str) -> Optional[InfraNode]:
        """Get a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def get_children(self, parent_id: str) -> List[InfraNode]:
        """Get all child nodes of a parent."""
        return [n for n in self.nodes if n.parent_id == parent_id]

    def get_edges_for_node(self, node_id: str) -> List[InfraEdge]:
        """Get all edges connected to a node."""
        return [e for e in self.edges if e.source == node_id or e.target == node_id]


# -----------------------------------------------------------------------------
# Reverse Engineering Result
# -----------------------------------------------------------------------------

class ReverseEngineeringResult(BaseModel):
    """
    Result of importing/parsing cloud inventory into InfraGraph.
    """
    success: bool = Field(..., description="Whether import was successful")
    graph: InfraGraph = Field(..., description="The parsed infrastructure graph")
    
    # Import statistics
    nodes_imported: int = Field(0, description="Number of nodes imported")
    edges_inferred: int = Field(0, description="Number of edges inferred")
    warnings: List[str] = Field(default_factory=list, description="Import warnings")
    errors: List[str] = Field(default_factory=list, description="Import errors")
    
    # Source info
    source_provider: CloudProvider = Field(..., description="Source cloud provider")
    import_timestamp: datetime = Field(default_factory=datetime.utcnow)


# -----------------------------------------------------------------------------
# Migration Models
# -----------------------------------------------------------------------------

class MigrationMapping(BaseModel):
    """
    Mapping of a single service from source to target cloud.
    """
    source_node_id: str = Field(..., description="Original node ID")
    source_service: str = Field(..., description="Source service type")
    target_service: str = Field(..., description="Target Azure service")
    target_resource_type: str = Field(..., description="Azure resource type")
    
    # Cost comparison
    source_monthly_cost: Optional[float] = Field(None, description="Source monthly cost (USD)")
    target_monthly_cost: Optional[float] = Field(None, description="Target monthly cost (USD)")
    cost_delta: Optional[float] = Field(None, description="Cost difference (positive = more expensive)")
    
    # Migration details
    migration_complexity: Severity = Field(Severity.MEDIUM, description="Migration complexity")
    migration_notes: Optional[str] = Field(None, description="Migration guidance")
    modernization_options: List[str] = Field(default_factory=list, description="PaaS upgrade options")
    
    # Risks and considerations
    risks: List[str] = Field(default_factory=list, description="Migration risks")
    prerequisites: List[str] = Field(default_factory=list, description="Prerequisites")

    class Config:
        use_enum_values = True


class MigrationResult(BaseModel):
    """
    Complete migration plan from source cloud to Azure.
    """
    success: bool = Field(..., description="Whether migration planning succeeded")
    source_provider: CloudProvider = Field(..., description="Source cloud provider")
    target_provider: CloudProvider = Field(CloudProvider.AZURE, description="Target cloud (always Azure)")
    
    # The graphs
    source_graph: InfraGraph = Field(..., description="Original infrastructure")
    target_graph: InfraGraph = Field(..., description="Migrated Azure infrastructure")
    
    # Mappings
    mappings: List[MigrationMapping] = Field(default_factory=list, description="Service-by-service mappings")
    
    # Cost summary
    source_monthly_total: float = Field(0.0, description="Total source monthly cost")
    target_monthly_total: float = Field(0.0, description="Total target monthly cost")
    total_savings: float = Field(0.0, description="Monthly savings (positive = cheaper on Azure)")
    savings_percent: Optional[float] = Field(None, description="Savings percentage")
    cost_summary_markdown: Optional[str] = Field(None, description="Human-readable cost summary")
    
    # Overall assessment
    overall_complexity: Severity = Field(Severity.MEDIUM, description="Overall migration complexity")
    estimated_duration_days: Optional[int] = Field(None, description="Estimated migration duration")
    key_risks: List[str] = Field(default_factory=list, description="Top migration risks")
    recommendations: List[str] = Field(default_factory=list, description="Migration recommendations")
    
    # Unmapped services
    unmapped_services: List[Dict[str, Any]] = Field(default_factory=list, description="Services without Azure equivalent")
    
    # IaC artifacts
    bicep_snippets: List[Dict[str, Any]] = Field(default_factory=list, description="Bicep code snippets")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True


# -----------------------------------------------------------------------------
# Compliance Models
# -----------------------------------------------------------------------------

class ComplianceViolation(BaseModel):
    """
    A single compliance violation.
    """
    id: str = Field(..., description="Unique violation ID")
    framework: str = Field(..., description="Compliance framework (ISO 27001, SOC 2, etc.)")
    requirement_id: str = Field(..., description="Framework requirement ID")
    title: str = Field(..., description="Violation title")
    description: str = Field(..., description="Violation description")
    
    affected_nodes: List[str] = Field(default_factory=list, description="Affected node IDs")
    severity: Severity = Field(..., description="Violation severity")
    
    remediation: str = Field(..., description="Remediation guidance")
    auto_fixable: bool = Field(False, description="Can be auto-fixed")
    fix_id: Optional[str] = Field(None, description="Fix ID for auto-fix")

    class Config:
        use_enum_values = True


class ComplianceReport(BaseModel):
    """
    Complete compliance analysis report.
    """
    frameworks: List[str] = Field(..., description="Analyzed frameworks")
    overall_score: int = Field(..., ge=0, le=100, description="Compliance score (0-100)")
    
    violations: List[ComplianceViolation] = Field(default_factory=list)
    compliant_controls: List[str] = Field(default_factory=list, description="Passed controls")
    
    recommendations: List[str] = Field(default_factory=list)
    
    # Statistics
    total_checks: int = Field(0)
    passed_checks: int = Field(0)
    failed_checks: int = Field(0)
    
    nodes_analyzed: int = Field(0)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# -----------------------------------------------------------------------------
# Cost Optimization Models
# -----------------------------------------------------------------------------

class NodeCost(BaseModel):
    """
    Cost information for a single node.
    """
    node_id: str = Field(..., description="Node ID")
    service_name: str = Field(..., description="Service name")
    
    current_sku: Optional[str] = Field(None, description="Current SKU/tier")
    current_monthly_cost: float = Field(0.0, description="Current monthly cost (USD)")
    
    recommended_sku: Optional[str] = Field(None, description="Recommended SKU/tier")
    recommended_monthly_cost: Optional[float] = Field(None, description="Recommended monthly cost")
    
    potential_savings: float = Field(0.0, description="Potential monthly savings")
    savings_percent: Optional[float] = Field(None, description="Savings percentage")
    
    cost_drivers: List[str] = Field(default_factory=list, description="What drives the cost")
    assumptions: Optional[str] = Field(None, description="Cost calculation assumptions")


class CostRecommendation(BaseModel):
    """
    A cost optimization recommendation.
    """
    id: str = Field(..., description="Recommendation ID")
    title: str = Field(..., description="Recommendation title")
    description: str = Field(..., description="Detailed description")
    
    affected_nodes: List[str] = Field(default_factory=list, description="Affected node IDs")
    category: str = Field(..., description="Category (right-sizing, reservations, etc.)")
    
    estimated_savings: float = Field(0.0, description="Estimated monthly savings (USD)")
    implementation_effort: Severity = Field(Severity.LOW, description="Implementation effort")
    
    auto_applicable: bool = Field(False, description="Can be auto-applied")
    fix_id: Optional[str] = Field(None, description="Fix ID for auto-apply")

    class Config:
        use_enum_values = True


class CostOptimization(BaseModel):
    """
    Complete cost analysis and optimization report.
    """
    currency: str = Field("USD", description="Currency for all costs")
    
    # Current state
    total_monthly_cost: float = Field(0.0, description="Total current monthly cost")
    cost_by_category: Dict[str, float] = Field(default_factory=dict, description="Cost breakdown by category")
    cost_by_service: Dict[str, float] = Field(default_factory=dict, description="Cost breakdown by service")
    
    # Per-node costs
    node_costs: List[NodeCost] = Field(default_factory=list)
    
    # Recommendations
    recommendations: List[CostRecommendation] = Field(default_factory=list)
    total_potential_savings: float = Field(0.0, description="Total potential monthly savings")
    savings_percent: Optional[float] = Field(None, description="Potential savings percentage")
    
    # Summary
    summary_markdown: Optional[str] = Field(None, description="Human-readable summary")
    top_cost_drivers: List[str] = Field(default_factory=list, description="Top cost drivers")
    
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


# -----------------------------------------------------------------------------
# Fix/Patch Models
# -----------------------------------------------------------------------------

class FixPatch(BaseModel):
    """
    A fix/patch that can be applied to the infrastructure graph.
    """
    id: str = Field(..., description="Unique fix ID")
    fix_type: FixType = Field(..., description="Type of fix")
    title: str = Field(..., description="Fix title")
    description: str = Field(..., description="What the fix does")
    
    # What changes
    affected_nodes: List[str] = Field(default_factory=list, description="Nodes to modify")
    node_patches: List[Dict[str, Any]] = Field(default_factory=list, description="Node property patches")
    new_nodes: List[InfraNode] = Field(default_factory=list, description="Nodes to add")
    new_edges: List[InfraEdge] = Field(default_factory=list, description="Edges to add")
    remove_nodes: List[str] = Field(default_factory=list, description="Node IDs to remove")
    remove_edges: List[str] = Field(default_factory=list, description="Edge IDs to remove")
    
    # Result
    applied: bool = Field(False, description="Whether fix was applied")
    applied_at: Optional[datetime] = Field(None)
    result_graph: Optional[InfraGraph] = Field(None, description="Graph after fix applied")
    
    # Metadata
    source: Optional[str] = Field(None, description="Source of fix (compliance, cost, etc.)")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        use_enum_values = True
