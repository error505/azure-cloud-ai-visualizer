"""
Migration Agent - AI-powered cloud migration planning

This module implements an AI agent using Microsoft Agent Framework to:
- Analyze source cloud infrastructure (AWS/GCP)
- Recommend optimal Azure service mappings
- Calculate cost comparisons
- Generate migration recommendations
"""

import json
import logging
from typing import Any, Dict, List, Optional
from pydantic import Field
from typing import Annotated

logger = logging.getLogger(__name__)

# Try to import agent framework components
try:
    from agent_framework import ChatAgent
except ImportError:
    ChatAgent = None
    logger.warning("agent_framework not available - migration agent will use fallback logic")


# Migration agent instructions
MIGRATION_AGENT_INSTRUCTIONS = """You are an expert Cloud Migration Architect specializing in AWS/GCP to Azure migrations.

Your role is to analyze source cloud infrastructure and recommend the optimal Azure equivalents.

When analyzing infrastructure, you should:
1. Understand the source service's purpose and capabilities
2. Identify the best Azure equivalent based on:
   - Feature parity
   - Performance characteristics
   - Cost efficiency
   - Integration with other Azure services
   - Azure Well-Architected Framework principles
3. Provide migration complexity assessment
4. Estimate cost differences
5. Highlight potential risks and considerations

For each service mapping, provide:
- Azure service recommendation with resource type
- Confidence level (high/medium/low)
- Estimated monthly cost comparison
- Migration complexity (simple/moderate/complex)
- Key migration considerations

Always respond with valid JSON in the following format:
{
  "mappings": [
    {
      "source_id": "node_id",
      "source_service": "AWS/GCP Service Name",
      "source_type": "service_type",
      "azure_service": "Azure Service Name",
      "azure_resource_type": "Microsoft.Xxx/yyy",
      "azure_icon_path": "/Icons/category/icon-name.svg",
      "confidence": "high|medium|low",
      "source_monthly_cost": 50.0,
      "azure_monthly_cost": 45.0,
      "complexity": "simple|moderate|complex",
      "considerations": ["consideration 1", "consideration 2"],
      "rationale": "Why this mapping is recommended"
    }
  ],
  "summary": {
    "total_source_cost": 500.0,
    "total_azure_cost": 450.0,
    "estimated_savings": 50.0,
    "savings_percent": 10.0,
    "overall_complexity": "moderate",
    "key_risks": ["risk 1", "risk 2"],
    "recommendations": ["recommendation 1", "recommendation 2"]
  }
}
"""


# Azure service catalog for AI reference
AZURE_SERVICE_CATALOG = {
    # Compute
    "virtual_machine": {
        "azure_service": "Azure Virtual Machines",
        "resource_type": "Microsoft.Compute/virtualMachines",
        "icon_path": "/Icons/compute/10021-icon-service-Virtual-Machine.svg",
        "category": "Compute",
        "base_cost": 48.5,
    },
    "function": {
        "azure_service": "Azure Functions",
        "resource_type": "Microsoft.Web/sites/functions",
        "icon_path": "/Icons/compute/10029-icon-service-Function-Apps.svg",
        "category": "Compute",
        "base_cost": 18.0,
    },
    # Containers
    "ecs_cluster": {
        "azure_service": "Azure Kubernetes Service",
        "resource_type": "Microsoft.ContainerService/managedClusters",
        "icon_path": "/Icons/containers/10023-icon-service-Kubernetes-Services.svg",
        "category": "Containers",
        "base_cost": 70.0,
    },
    "kubernetes": {
        "azure_service": "Azure Kubernetes Service",
        "resource_type": "Microsoft.ContainerService/managedClusters",
        "icon_path": "/Icons/containers/10023-icon-service-Kubernetes-Services.svg",
        "category": "Containers",
        "base_cost": 70.0,
    },
    "container_registry": {
        "azure_service": "Azure Container Registry",
        "resource_type": "Microsoft.ContainerRegistry/registries",
        "icon_path": "/Icons/containers/10105-icon-service-Container-Registries.svg",
        "category": "Containers",
        "base_cost": 5.0,
    },
    # Database
    "rds": {
        "azure_service": "Azure SQL Database",
        "resource_type": "Microsoft.Sql/servers/databases",
        "icon_path": "/Icons/databases/10130-icon-service-SQL-Database.svg",
        "category": "Database",
        "base_cost": 45.0,
    },
    "dynamodb": {
        "azure_service": "Azure Cosmos DB",
        "resource_type": "Microsoft.DocumentDB/databaseAccounts",
        "icon_path": "/Icons/databases/10121-icon-service-Azure-Cosmos-DB.svg",
        "category": "Database",
        "base_cost": 50.0,
    },
    "elasticache": {
        "azure_service": "Azure Cache for Redis",
        "resource_type": "Microsoft.Cache/Redis",
        "icon_path": "/Icons/databases/10137-icon-service-Cache-Redis.svg",
        "category": "Database",
        "base_cost": 40.0,
    },
    # Storage
    "object_storage": {
        "azure_service": "Azure Blob Storage",
        "resource_type": "Microsoft.Storage/storageAccounts",
        "icon_path": "/Icons/storage/10086-icon-service-Storage-Accounts.svg",
        "category": "Storage",
        "base_cost": 20.0,
    },
    # Networking
    "vpc": {
        "azure_service": "Azure Virtual Network",
        "resource_type": "Microsoft.Network/virtualNetworks",
        "icon_path": "/Icons/networking/10061-icon-service-Virtual-Networks.svg",
        "category": "Networking",
        "base_cost": 0.0,
    },
    "load_balancer": {
        "azure_service": "Azure Load Balancer",
        "resource_type": "Microsoft.Network/loadBalancers",
        "icon_path": "/Icons/networking/10062-icon-service-Load-Balancers.svg",
        "category": "Networking",
        "base_cost": 18.0,
    },
    "cloudfront": {
        "azure_service": "Azure Front Door",
        "resource_type": "Microsoft.Cdn/profiles",
        "icon_path": "/Icons/networking/10073-icon-service-Front-Doors.svg",
        "category": "Networking",
        "base_cost": 32.0,
    },
    "api_gateway": {
        "azure_service": "Azure API Management",
        "resource_type": "Microsoft.ApiManagement/service",
        "icon_path": "/Icons/integration/10042-icon-service-API-Management-Services.svg",
        "category": "Integration",
        "base_cost": 40.0,
    },
    # Integration
    "queue": {
        "azure_service": "Azure Service Bus",
        "resource_type": "Microsoft.ServiceBus/namespaces",
        "icon_path": "/Icons/integration/10836-icon-service-Service-Bus.svg",
        "category": "Integration",
        "base_cost": 10.0,
    },
    "topic": {
        "azure_service": "Azure Service Bus",
        "resource_type": "Microsoft.ServiceBus/namespaces",
        "icon_path": "/Icons/integration/10836-icon-service-Service-Bus.svg",
        "category": "Integration",
        "base_cost": 10.0,
    },
    "step_functions": {
        "azure_service": "Azure Logic Apps",
        "resource_type": "Microsoft.Logic/workflows",
        "icon_path": "/Icons/integration/10201-icon-service-Logic-Apps.svg",
        "category": "Integration",
        "base_cost": 15.0,
    },
    # Security
    "security_group": {
        "azure_service": "Network Security Group",
        "resource_type": "Microsoft.Network/networkSecurityGroups",
        "icon_path": "/Icons/networking/10067-icon-service-Network-Security-Groups.svg",
        "category": "Security",
        "base_cost": 0.0,
    },
    "secrets_manager": {
        "azure_service": "Azure Key Vault",
        "resource_type": "Microsoft.KeyVault/vaults",
        "icon_path": "/Icons/security/10245-icon-service-Key-Vaults.svg",
        "category": "Security",
        "base_cost": 3.0,
    },
    "kms": {
        "azure_service": "Azure Key Vault",
        "resource_type": "Microsoft.KeyVault/vaults",
        "icon_path": "/Icons/security/10245-icon-service-Key-Vaults.svg",
        "category": "Security",
        "base_cost": 3.0,
    },
    # Identity
    "cognito": {
        "azure_service": "Azure AD B2C",
        "resource_type": "Microsoft.AzureActiveDirectory/b2cDirectories",
        "icon_path": "/Icons/identity/10221-icon-service-Azure-AD-B2C.svg",
        "category": "Identity",
        "base_cost": 50.0,
    },
    "iam_role": {
        "azure_service": "Azure Managed Identity",
        "resource_type": "Microsoft.ManagedIdentity/userAssignedIdentities",
        "icon_path": "/Icons/identity/10227-icon-service-Managed-Identities.svg",
        "category": "Identity",
        "base_cost": 0.0,
    },
    # AI/ML
    "sagemaker": {
        "azure_service": "Azure Machine Learning",
        "resource_type": "Microsoft.MachineLearningServices/workspaces",
        "icon_path": "/Icons/ai + machine learning/10167-icon-service-Machine-Learning.svg",
        "category": "AI",
        "base_cost": 100.0,
    },
}


def analyze_migration_with_ai_tool(
    source_nodes: Annotated[List[Dict], Field(description="List of source cloud nodes with id, label, serviceType, provider")],
    source_provider: Annotated[str, Field(description="Source cloud provider: aws or gcp")],
) -> str:
    """AI tool to analyze source cloud infrastructure and recommend Azure mappings."""
    
    # Build a detailed analysis prompt
    nodes_desc = []
    for node in source_nodes:
        nodes_desc.append(f"- {node.get('label', 'Unknown')} (type: {node.get('serviceType', 'unknown')}, id: {node.get('id', 'unknown')})")
    
    nodes_text = "\n".join(nodes_desc)
    
    return f"""Analyze these {source_provider.upper()} services and provide Azure migration recommendations:

{nodes_text}

For each service, provide the optimal Azure equivalent considering:
1. Feature parity and functionality
2. Cost optimization
3. Azure Well-Architected Framework alignment
4. Integration capabilities

Respond with a JSON object containing 'mappings' array and 'summary' object."""


class MigrationAgent:
    """AI-powered migration planning agent using Microsoft Agent Framework."""
    
    def __init__(self, agent_client):
        self.agent_client = agent_client
        self.chat_agent = None
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize the migration agent with tools."""
        if self._initialized:
            return
            
        logger.info("Initializing Migration Agent...")
        
        tools = [analyze_migration_with_ai_tool]
        
        try:
            create_fn = getattr(self.agent_client, "create_agent", None)
            if callable(create_fn):
                try:
                    self.chat_agent = create_fn(
                        name="MigrationAgent",
                        instructions=MIGRATION_AGENT_INSTRUCTIONS,
                        tools=tools
                    )
                except TypeError:
                    self.chat_agent = create_fn(
                        instructions=MIGRATION_AGENT_INSTRUCTIONS,
                        tools=tools
                    )
            else:
                self.chat_agent = getattr(self.agent_client, "chat", None) or getattr(self.agent_client, "run", None)
            
            self._initialized = True
            logger.info("Migration Agent initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Migration Agent: {e}")
            raise
    
    async def analyze_migration(
        self,
        source_nodes: List[Dict[str, Any]],
        source_provider: str,
    ) -> Dict[str, Any]:
        """
        Analyze source infrastructure and generate AI-powered Azure migration plan.
        
        Args:
            source_nodes: List of source cloud nodes
            source_provider: Source cloud provider (aws/gcp)
            
        Returns:
            Migration plan with mappings, costs, and recommendations
        """
        if not self._initialized:
            await self.initialize()
        
        # Build prompt for the AI agent
        nodes_summary = []
        for node in source_nodes:
            data = node.get("data", {})
            nodes_summary.append({
                "id": node.get("id"),
                "label": data.get("label") or data.get("title") or node.get("id"),
                "serviceType": data.get("serviceType"),
                "category": data.get("category"),
                "provider": source_provider,
            })
        
        prompt = f"""Analyze this {source_provider.upper()} infrastructure and recommend Azure migration:

Source Infrastructure ({len(nodes_summary)} services):
{json.dumps(nodes_summary, indent=2)}

Provide a comprehensive migration plan with:
1. Azure service mapping for each source service
2. Cost comparison (estimated monthly costs)
3. Migration complexity assessment
4. Key risks and recommendations

Return a valid JSON response with 'mappings' and 'summary' keys."""

        try:
            if self.chat_agent:
                # Use AI agent for analysis
                logger.info(f"[MigrationAgent] Calling AI for migration analysis of {len(nodes_summary)} nodes")
                response = await self.chat_agent.run(prompt)
                
                # Extract result from response
                result_text = getattr(response, "result", None) or getattr(response, "text", None) or str(response)
                
                # Try to parse JSON from response
                try:
                    # Find JSON in response
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', result_text)
                    if json_match:
                        return json.loads(json_match.group())
                except json.JSONDecodeError:
                    logger.warning("Failed to parse AI response as JSON, using fallback")
            
            # Fallback to rule-based mapping if AI fails
            return self._fallback_mapping(nodes_summary, source_provider)
            
        except Exception as e:
            logger.error(f"Error in AI migration analysis: {e}")
            return self._fallback_mapping(nodes_summary, source_provider)
    
    def _fallback_mapping(
        self,
        nodes_summary: List[Dict],
        source_provider: str,
    ) -> Dict[str, Any]:
        """Fallback to rule-based mapping when AI is unavailable."""
        logger.info("[MigrationAgent] Using fallback rule-based mapping")
        
        mappings = []
        total_source_cost = 0.0
        total_azure_cost = 0.0
        
        for node in nodes_summary:
            service_type = node.get("serviceType", "unknown")
            catalog_entry = AZURE_SERVICE_CATALOG.get(service_type)
            
            if catalog_entry:
                # Estimate source cost (rough approximation)
                source_cost = catalog_entry["base_cost"] * 1.1  # AWS/GCP typically 10% more
                azure_cost = catalog_entry["base_cost"]
                
                mappings.append({
                    "source_id": node.get("id"),
                    "source_service": node.get("label"),
                    "source_type": service_type,
                    "azure_service": catalog_entry["azure_service"],
                    "azure_resource_type": catalog_entry["resource_type"],
                    "azure_icon_path": catalog_entry["icon_path"],
                    "azure_category": catalog_entry["category"],
                    "confidence": "high",
                    "source_monthly_cost": round(source_cost, 2),
                    "azure_monthly_cost": round(azure_cost, 2),
                    "complexity": "moderate",
                    "considerations": [
                        f"Review {source_provider.upper()} specific configurations",
                        "Test in Azure staging environment before production",
                    ],
                    "rationale": f"Direct equivalent service mapping from {source_provider.upper()} to Azure",
                })
                
                total_source_cost += source_cost
                total_azure_cost += azure_cost
            else:
                # Unknown service
                mappings.append({
                    "source_id": node.get("id"),
                    "source_service": node.get("label"),
                    "source_type": service_type,
                    "azure_service": "Manual Review Required",
                    "azure_resource_type": None,
                    "azure_icon_path": None,
                    "azure_category": "Other",
                    "confidence": "low",
                    "source_monthly_cost": 0,
                    "azure_monthly_cost": 0,
                    "complexity": "complex",
                    "considerations": [
                        "No automatic mapping available",
                        "Requires manual architecture review",
                    ],
                    "rationale": "Service type not in migration catalog",
                })
        
        savings = total_source_cost - total_azure_cost
        savings_percent = (savings / total_source_cost * 100) if total_source_cost > 0 else 0
        
        return {
            "mappings": mappings,
            "summary": {
                "total_source_cost": round(total_source_cost, 2),
                "total_azure_cost": round(total_azure_cost, 2),
                "estimated_savings": round(savings, 2),
                "savings_percent": round(savings_percent, 2),
                "overall_complexity": "moderate",
                "key_risks": [
                    "Data migration may require additional planning",
                    "Some service-specific features may differ",
                ],
                "recommendations": [
                    "Conduct pilot migration with non-critical workloads first",
                    "Review Azure Well-Architected Framework for optimization opportunities",
                    "Consider Azure Hybrid Benefit for cost savings",
                ],
            },
            "agent_used": False,
            "method": "fallback_rules",
        }
    
    async def stream_analysis(
        self,
        source_nodes: List[Dict[str, Any]],
        source_provider: str,
    ):
        """Stream migration analysis for real-time updates."""
        if not self._initialized:
            await self.initialize()
        
        nodes_summary = []
        for node in source_nodes:
            data = node.get("data", {})
            nodes_summary.append({
                "id": node.get("id"),
                "label": data.get("label") or data.get("title"),
                "serviceType": data.get("serviceType"),
            })
        
        prompt = f"""Analyze this {source_provider.upper()} infrastructure for Azure migration:
{json.dumps(nodes_summary, indent=2)}

For each service, recommend the optimal Azure equivalent with cost comparison."""

        try:
            if self.chat_agent and hasattr(self.chat_agent, 'run_stream'):
                async for chunk in self.chat_agent.run_stream(prompt):
                    text = getattr(chunk, 'text', None) or getattr(chunk, 'data', None)
                    if text:
                        yield str(text)
            else:
                # Fallback - yield complete result
                result = await self.analyze_migration(source_nodes, source_provider)
                yield json.dumps(result, indent=2)
        except Exception as e:
            logger.error(f"Error in stream analysis: {e}")
            yield f"Error: {str(e)}"


# Singleton instance
_migration_agent: Optional[MigrationAgent] = None


async def get_migration_agent() -> MigrationAgent:
    """Get or create the migration agent singleton."""
    global _migration_agent
    
    if _migration_agent is None:
        from app.deps import get_agent_client
        
        try:
            client = get_agent_client()
            _migration_agent = MigrationAgent(client)
            await _migration_agent.initialize()
        except Exception as e:
            logger.error(f"Failed to create migration agent: {e}")
            # Create agent without AI client for fallback
            _migration_agent = MigrationAgent(None)
    
    return _migration_agent
