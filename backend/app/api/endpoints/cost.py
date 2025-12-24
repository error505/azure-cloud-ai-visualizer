"""
Cost Optimization API Endpoints

Endpoints:
- POST /api/cost/analyze - Analyze diagram for cost optimization opportunities
- GET /api/cost/recommendations - Get available cost optimization strategies
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from app.models.infra_models import (
    CloudProvider,
    Severity,
    NodeCost,
    CostRecommendation,
    CostOptimization,
)
from app.deps import get_agent_client

logger = logging.getLogger(__name__)

router = APIRouter()


# -----------------------------------------------------------------------------
# Cost Estimation Data
# -----------------------------------------------------------------------------

# Average monthly costs by Azure service type (USD)
AZURE_SERVICE_COSTS: Dict[str, Dict[str, Any]] = {
    "virtual_machine": {
        "base_cost": 50.0,
        "category": "Compute",
        "sku_options": {
            "B2s": 30.0,
            "D2s_v3": 70.0,
            "D4s_v3": 140.0,
            "D8s_v3": 280.0,
        },
        "optimization_tips": [
            "Consider Reserved Instances for 1-3 year commitment (up to 72% savings)",
            "Use Spot instances for fault-tolerant workloads (up to 90% savings)",
            "Right-size based on CPU/memory utilization",
            "Auto-shutdown dev/test VMs outside business hours",
        ],
    },
    "app_service": {
        "base_cost": 55.0,
        "category": "Compute",
        "sku_options": {
            "B1": 13.0,
            "S1": 73.0,
            "P1v2": 146.0,
            "P2v2": 292.0,
        },
        "optimization_tips": [
            "Use Free/Shared tiers for dev/test",
            "Scale down during off-peak hours",
            "Consider Azure Functions for event-driven workloads",
        ],
    },
    "function_app": {
        "base_cost": 15.0,
        "category": "Compute",
        "optimization_tips": [
            "Consumption plan for sporadic workloads",
            "Premium plan for consistent load with VNET integration needs",
            "Optimize function execution time and memory",
        ],
    },
    "kubernetes": {
        "base_cost": 150.0,
        "category": "Containers",
        "sku_options": {
            "Standard_B2s": 100.0,
            "Standard_D2s_v3": 200.0,
            "Standard_D4s_v3": 400.0,
        },
        "optimization_tips": [
            "Use cluster autoscaler to match demand",
            "Implement pod autoscaling (HPA/VPA)",
            "Use Spot node pools for non-critical workloads",
            "Consider Azure Container Apps for simpler workloads",
        ],
    },
    "storage_account": {
        "base_cost": 25.0,
        "category": "Storage",
        "sku_options": {
            "Standard_LRS": 20.0,
            "Standard_GRS": 40.0,
            "Premium_LRS": 100.0,
        },
        "optimization_tips": [
            "Use lifecycle management to tier cold data",
            "Enable soft delete only when needed",
            "Use Cool/Archive tiers for infrequent access",
            "Consider reserved capacity for predictable usage",
        ],
    },
    "sql_database": {
        "base_cost": 150.0,
        "category": "Database",
        "sku_options": {
            "Basic": 5.0,
            "S0": 15.0,
            "S3": 75.0,
            "P1": 465.0,
        },
        "optimization_tips": [
            "Use serverless for intermittent workloads",
            "Right-size DTU/vCore based on actual usage",
            "Use elastic pools for multiple databases",
            "Consider Hyperscale for large, growing databases",
        ],
    },
    "cosmos_db": {
        "base_cost": 100.0,
        "category": "Database",
        "optimization_tips": [
            "Use serverless for dev/test and low-traffic apps",
            "Optimize partition key for even distribution",
            "Use autoscale for variable workloads",
            "Consider reserved capacity for steady throughput",
        ],
    },
    "redis_cache": {
        "base_cost": 40.0,
        "category": "Database",
        "sku_options": {
            "Basic_C0": 16.0,
            "Standard_C1": 40.0,
            "Premium_P1": 180.0,
        },
        "optimization_tips": [
            "Use Basic tier for dev/test only",
            "Right-size cache based on memory and connection needs",
            "Enable data persistence only when required",
        ],
    },
    "api_management": {
        "base_cost": 50.0,
        "category": "Integration",
        "sku_options": {
            "Consumption": 3.5,
            "Developer": 50.0,
            "Basic": 150.0,
            "Standard": 700.0,
        },
        "optimization_tips": [
            "Use Consumption tier for low-volume APIs",
            "Developer tier for non-production only",
            "Consider self-hosted gateway for hybrid scenarios",
        ],
    },
    "service_bus": {
        "base_cost": 10.0,
        "category": "Integration",
        "optimization_tips": [
            "Use Basic tier for simple queues",
            "Standard tier for topics and most scenarios",
            "Premium only for mission-critical with isolation needs",
        ],
    },
    "key_vault": {
        "base_cost": 3.0,
        "category": "Security",
        "optimization_tips": [
            "Standard tier is sufficient for most use cases",
            "Premium tier only for HSM-backed keys",
            "Consolidate secrets to reduce vault count",
        ],
    },
    "log_analytics": {
        "base_cost": 75.0,
        "category": "Monitoring",
        "optimization_tips": [
            "Set appropriate data retention periods",
            "Use data collection rules to filter ingestion",
            "Consider commitment tiers for predictable volume",
            "Archive old data to storage for compliance",
        ],
    },
    "app_insights": {
        "base_cost": 25.0,
        "category": "Monitoring",
        "optimization_tips": [
            "Use sampling to reduce data volume",
            "Set daily caps for dev/test environments",
            "Disable unnecessary telemetry collection",
        ],
    },
}


# -----------------------------------------------------------------------------
# Request/Response Models
# -----------------------------------------------------------------------------

class CostAnalyzeRequest(BaseModel):
    """Request to analyze costs."""
    project_id: str = Field(..., description="Project ID")
    diagram: Dict[str, Any] = Field(..., description="Diagram with nodes and edges")
    options: Optional[Dict[str, Any]] = Field(None, description="Analysis options")


class NodeCostResponse(BaseModel):
    """Cost info for a single node."""
    node_id: str
    service_name: str
    category: str
    current_sku: Optional[str] = None
    current_monthly_cost: float
    recommended_sku: Optional[str] = None
    recommended_monthly_cost: Optional[float] = None
    potential_savings: float
    savings_percent: Optional[float] = None
    cost_drivers: List[str] = Field(default_factory=list)
    optimization_tips: List[str] = Field(default_factory=list)


class CostRecommendationResponse(BaseModel):
    """Cost optimization recommendation."""
    id: str
    title: str
    description: str
    affected_nodes: List[str]
    category: str
    estimated_savings: float
    implementation_effort: str
    auto_applicable: bool = False


class CostOptimizationResponse(BaseModel):
    """Complete cost analysis response."""
    currency: str = "USD"
    total_monthly_cost: float
    cost_by_category: Dict[str, float]
    cost_by_service: Dict[str, float]
    node_costs: List[NodeCostResponse]
    recommendations: List[CostRecommendationResponse]
    total_potential_savings: float
    savings_percent: Optional[float] = None
    summary_markdown: str
    top_cost_drivers: List[str]
    analyzed_at: str


class OptimizationStrategyResponse(BaseModel):
    """Available optimization strategy."""
    id: str
    name: str
    description: str
    category: str
    typical_savings_percent: float
    implementation_effort: str
    applicable_services: List[str]


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _estimate_node_cost(node: Dict[str, Any]) -> NodeCostResponse:
    """Estimate cost for a single node based on service type."""
    data = node.get("data", {})
    node_id = node.get("id", "unknown")
    
    # Determine service type
    service_type = (
        data.get("service_type") or 
        data.get("serviceType") or
        data.get("resourceType", "").split("/")[-1].lower() or
        data.get("title", "").lower().replace(" ", "_") or
        "unknown"
    )
    
    # Normalize service type
    service_type_normalized = service_type.lower().replace(" ", "_").replace("-", "_")
    
    # Find matching cost data
    cost_data = None
    for key, value in AZURE_SERVICE_COSTS.items():
        if key in service_type_normalized or service_type_normalized in key:
            cost_data = value
            break
    
    if not cost_data:
        # Default cost for unknown services
        return NodeCostResponse(
            node_id=node_id,
            service_name=data.get("title", data.get("label", service_type)),
            category="Other",
            current_monthly_cost=20.0,
            potential_savings=0,
            optimization_tips=["Review service usage and consider consolidation"],
        )
    
    # Get current SKU if specified
    current_sku = data.get("sku") or data.get("tier")
    sku_options = cost_data.get("sku_options", {})
    
    # Calculate current cost
    if current_sku and current_sku in sku_options:
        current_cost = sku_options[current_sku]
    else:
        current_cost = cost_data["base_cost"]
    
    # Find cheapest viable option
    recommended_sku = None
    recommended_cost = None
    potential_savings = 0
    
    if sku_options:
        # Sort by cost
        sorted_skus = sorted(sku_options.items(), key=lambda x: x[1])
        if sorted_skus:
            cheapest = sorted_skus[0]
            if cheapest[1] < current_cost:
                recommended_sku = cheapest[0]
                recommended_cost = cheapest[1]
                potential_savings = current_cost - recommended_cost
    
    savings_percent = None
    if potential_savings > 0 and current_cost > 0:
        savings_percent = (potential_savings / current_cost) * 100
    
    return NodeCostResponse(
        node_id=node_id,
        service_name=data.get("title", data.get("label", service_type)),
        category=cost_data.get("category", "Other"),
        current_sku=current_sku,
        current_monthly_cost=current_cost,
        recommended_sku=recommended_sku,
        recommended_monthly_cost=recommended_cost,
        potential_savings=potential_savings,
        savings_percent=savings_percent,
        cost_drivers=[f"Base service cost", "SKU tier selection"],
        optimization_tips=cost_data.get("optimization_tips", []),
    )


def _generate_recommendations(node_costs: List[NodeCostResponse]) -> List[CostRecommendationResponse]:
    """Generate high-level cost optimization recommendations."""
    recommendations = []
    
    # Group by category
    by_category: Dict[str, List[NodeCostResponse]] = {}
    for nc in node_costs:
        by_category.setdefault(nc.category, []).append(nc)
    
    # Recommendation 1: Reserved Instances for Compute
    compute_nodes = by_category.get("Compute", [])
    if compute_nodes:
        compute_cost = sum(n.current_monthly_cost for n in compute_nodes)
        recommendations.append(CostRecommendationResponse(
            id=str(uuid.uuid4())[:8],
            title="Consider Reserved Instances for Compute",
            description=f"Your compute resources cost ${compute_cost:.0f}/month. Reserved Instances can save 30-72% for 1-3 year commitments.",
            affected_nodes=[n.node_id for n in compute_nodes],
            category="Reserved Capacity",
            estimated_savings=compute_cost * 0.40,  # Assume 40% average savings
            implementation_effort="low",
        ))
    
    # Recommendation 2: Right-sizing
    oversized = [n for n in node_costs if n.potential_savings > 10]
    if oversized:
        total_savings = sum(n.potential_savings for n in oversized)
        recommendations.append(CostRecommendationResponse(
            id=str(uuid.uuid4())[:8],
            title="Right-size Underutilized Resources",
            description=f"Found {len(oversized)} resources that may be over-provisioned. Consider downsizing based on actual usage.",
            affected_nodes=[n.node_id for n in oversized],
            category="Right-sizing",
            estimated_savings=total_savings,
            implementation_effort="medium",
        ))
    
    # Recommendation 3: Dev/Test discounts
    dev_test_candidates = [n for n in node_costs if n.current_monthly_cost > 50]
    if dev_test_candidates:
        recommendations.append(CostRecommendationResponse(
            id=str(uuid.uuid4())[:8],
            title="Apply Dev/Test Pricing",
            description="If any environments are non-production, consider Azure Dev/Test pricing for up to 55% savings on Windows VMs and discounted rates on other services.",
            affected_nodes=[n.node_id for n in dev_test_candidates],
            category="Licensing",
            estimated_savings=sum(n.current_monthly_cost for n in dev_test_candidates) * 0.30,
            implementation_effort="low",
        ))
    
    # Recommendation 4: Auto-shutdown for VMs
    vm_nodes = [n for n in node_costs if "virtual_machine" in n.service_name.lower() or "vm" in n.service_name.lower()]
    if vm_nodes:
        recommendations.append(CostRecommendationResponse(
            id=str(uuid.uuid4())[:8],
            title="Enable Auto-shutdown for Dev/Test VMs",
            description="Automatically shut down VMs outside business hours to save up to 70% on compute costs.",
            affected_nodes=[n.node_id for n in vm_nodes],
            category="Automation",
            estimated_savings=sum(n.current_monthly_cost for n in vm_nodes) * 0.50,  # Assume 12 hours off = 50% savings
            implementation_effort="low",
            auto_applicable=True,
        ))
    
    # Recommendation 5: Storage tiering
    storage_nodes = by_category.get("Storage", [])
    if storage_nodes:
        recommendations.append(CostRecommendationResponse(
            id=str(uuid.uuid4())[:8],
            title="Implement Storage Lifecycle Management",
            description="Use lifecycle policies to automatically tier data to Cool or Archive storage based on access patterns.",
            affected_nodes=[n.node_id for n in storage_nodes],
            category="Storage Optimization",
            estimated_savings=sum(n.current_monthly_cost for n in storage_nodes) * 0.40,
            implementation_effort="medium",
        ))
    
    return recommendations


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@router.post("/cost/analyze", response_model=CostOptimizationResponse)
async def analyze_costs(request: CostAnalyzeRequest):
    """
    Analyze diagram for cost optimization opportunities.
    
    Returns detailed cost breakdown, per-node analysis, and
    actionable recommendations for reducing spend.
    """
    try:
        logger.info(f"Analyzing costs for project {request.project_id}")
        
        nodes = request.diagram.get("nodes", [])
        if not nodes:
            raise HTTPException(status_code=400, detail="No nodes in diagram to analyze")
        
        # Analyze each node
        node_costs = [_estimate_node_cost(node) for node in nodes]
        
        # Calculate totals
        total_cost = sum(n.current_monthly_cost for n in node_costs)
        total_potential_savings = sum(n.potential_savings for n in node_costs)
        
        # Group by category and service
        cost_by_category: Dict[str, float] = {}
        cost_by_service: Dict[str, float] = {}
        for nc in node_costs:
            cost_by_category[nc.category] = cost_by_category.get(nc.category, 0) + nc.current_monthly_cost
            cost_by_service[nc.service_name] = cost_by_service.get(nc.service_name, 0) + nc.current_monthly_cost
        
        # Generate recommendations
        recommendations = _generate_recommendations(node_costs)
        total_rec_savings = sum(r.estimated_savings for r in recommendations)
        
        # Top cost drivers
        sorted_services = sorted(cost_by_service.items(), key=lambda x: x[1], reverse=True)
        top_drivers = [f"{svc}: ${cost:.0f}/mo" for svc, cost in sorted_services[:5]]
        
        # Summary
        savings_percent = None
        if total_cost > 0:
            savings_percent = (total_rec_savings / total_cost) * 100
        
        summary_lines = [
            f"**Total Monthly Cost:** ${total_cost:,.2f}",
            f"**Potential Savings:** ${total_rec_savings:,.2f}" + (f" ({savings_percent:.1f}%)" if savings_percent else ""),
            "",
            "**Cost by Category:**",
        ]
        for cat, cost in sorted(cost_by_category.items(), key=lambda x: x[1], reverse=True):
            pct = (cost / total_cost * 100) if total_cost > 0 else 0
            summary_lines.append(f"- {cat}: ${cost:,.2f} ({pct:.1f}%)")
        
        logger.info(f"Cost analysis complete: ${total_cost:.2f}/mo, {len(recommendations)} recommendations")
        
        return CostOptimizationResponse(
            currency="USD",
            total_monthly_cost=total_cost,
            cost_by_category=cost_by_category,
            cost_by_service=cost_by_service,
            node_costs=node_costs,
            recommendations=recommendations,
            total_potential_savings=total_rec_savings,
            savings_percent=savings_percent,
            summary_markdown="\n".join(summary_lines),
            top_cost_drivers=top_drivers,
            analyzed_at=datetime.utcnow().isoformat(),
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing costs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Cost analysis failed: {str(e)}")


@router.get("/cost/strategies", response_model=List[OptimizationStrategyResponse])
async def get_optimization_strategies():
    """
    Get available cost optimization strategies.
    
    Returns list of strategies with typical savings and applicability.
    """
    strategies = [
        OptimizationStrategyResponse(
            id="reserved-instances",
            name="Reserved Instances",
            description="Commit to 1 or 3 year terms for significant discounts on compute resources",
            category="Reserved Capacity",
            typical_savings_percent=40,
            implementation_effort="low",
            applicable_services=["Virtual Machines", "SQL Database", "Cosmos DB", "App Service"],
        ),
        OptimizationStrategyResponse(
            id="spot-instances",
            name="Spot Instances",
            description="Use spare Azure capacity at deep discounts for fault-tolerant workloads",
            category="Compute Optimization",
            typical_savings_percent=80,
            implementation_effort="medium",
            applicable_services=["Virtual Machines", "AKS Node Pools", "Batch"],
        ),
        OptimizationStrategyResponse(
            id="auto-shutdown",
            name="Auto-shutdown",
            description="Automatically stop dev/test resources outside business hours",
            category="Automation",
            typical_savings_percent=50,
            implementation_effort="low",
            applicable_services=["Virtual Machines", "AKS Clusters"],
        ),
        OptimizationStrategyResponse(
            id="right-sizing",
            name="Right-sizing",
            description="Match resource size to actual utilization patterns",
            category="Right-sizing",
            typical_savings_percent=30,
            implementation_effort="medium",
            applicable_services=["Virtual Machines", "SQL Database", "App Service", "AKS"],
        ),
        OptimizationStrategyResponse(
            id="storage-tiering",
            name="Storage Tiering",
            description="Move infrequently accessed data to Cool or Archive tiers",
            category="Storage Optimization",
            typical_savings_percent=60,
            implementation_effort="medium",
            applicable_services=["Storage Accounts", "Blob Storage"],
        ),
        OptimizationStrategyResponse(
            id="serverless",
            name="Serverless Migration",
            description="Move suitable workloads to consumption-based serverless services",
            category="Architecture",
            typical_savings_percent=40,
            implementation_effort="high",
            applicable_services=["Azure Functions", "Logic Apps", "Cosmos DB Serverless"],
        ),
        OptimizationStrategyResponse(
            id="hybrid-benefit",
            name="Azure Hybrid Benefit",
            description="Use existing Windows Server or SQL Server licenses on Azure",
            category="Licensing",
            typical_savings_percent=40,
            implementation_effort="low",
            applicable_services=["Virtual Machines", "SQL Database", "SQL Managed Instance"],
        ),
    ]
    return strategies


@router.get("/cost/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "cost-optimization"}
