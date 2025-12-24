"""
Cloud Inventory Parsers

Normalize cloud inventory JSON exports into unified InfraGraph format.
Supports:
- Azure Resource Graph / ARM exports
- AWS CloudFormation / Resource Explorer exports  
- GCP Cloud Asset Inventory exports

Each parser handles provider-specific formats and normalizes them into
InfraNode/InfraEdge structures that can be used for migration planning,
compliance analysis, and cost optimization.
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..models.infra_models import (
    CloudProvider,
    EdgeType,
    InfraEdge,
    InfraGraph,
    InfraNode,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Icon Path Mappings
# -----------------------------------------------------------------------------

# AWS service type to icon path
AWS_ICON_PATHS: Dict[str, str] = {
    # Compute
    "virtual_machine": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Compute/64/Arch_Amazon-EC2_64.svg",
    "function": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Compute/64/Arch_AWS-Lambda_64.svg",
    
    # Containers
    "ecs_cluster": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Containers/64/Arch_Amazon-Elastic-Container-Service_64.svg",
    "ecs_service": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Containers/64/Arch_Amazon-Elastic-Container-Service_64.svg",
    "ecs_task": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Containers/64/Arch_Amazon-Elastic-Container-Service_64.svg",
    "kubernetes": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Containers/64/Arch_Amazon-Elastic-Kubernetes-Service_64.svg",
    "container_registry": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Containers/64/Arch_Amazon-Elastic-Container-Registry_64.svg",
    
    # Database
    "rds": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Database/64/Arch_Amazon-RDS_64.svg",
    "rds_cluster": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Database/64/Arch_Amazon-Aurora_64.svg",
    "dynamodb": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Database/64/Arch_Amazon-DynamoDB_64.svg",
    "elasticache": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Database/64/Arch_Amazon-ElastiCache_64.svg",
    
    # Storage
    "object_storage": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Storage/64/Arch_Amazon-Simple-Storage-Service_64.svg",
    
    # Networking
    "vpc": "/aws_icons/Architecture-Group-Icons_07312025/Virtual-private-cloud-VPC_32.svg",
    "subnet": "/aws_icons/Architecture-Group-Icons_07312025/Public-subnet_32.svg",
    "load_balancer": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Networking-Content-Delivery/64/Arch_Elastic-Load-Balancing_64.svg",
    "target_group": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Networking-Content-Delivery/64/Arch_Elastic-Load-Balancing_64.svg",
    "internet_gateway": "/aws_icons/Resource-Icons_07312025/Res_Networking-Content-Delivery/Res_48_Dark/Res_Amazon-VPC_Internet-Gateway_48_Dark.svg",
    "nat_gateway": "/aws_icons/Resource-Icons_07312025/Res_Networking-Content-Delivery/Res_48_Dark/Res_Amazon-VPC_NAT-Gateway_48_Dark.svg",
    "route_table": "/aws_icons/Resource-Icons_07312025/Res_Networking-Content-Delivery/Res_48_Dark/Res_Amazon-VPC_Router_48_Dark.svg",
    "cloudfront": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Networking-Content-Delivery/64/Arch_Amazon-CloudFront_64.svg",
    "route53": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Networking-Content-Delivery/64/Arch_Amazon-Route-53_64.svg",
    "api_gateway": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Networking-Content-Delivery/64/Arch_Amazon-API-Gateway_64.svg",
    "api_gateway_v2": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Networking-Content-Delivery/64/Arch_Amazon-API-Gateway_64.svg",
    
    # Security
    "security_group": "/aws_icons/Resource-Icons_07312025/Res_Security-Identity-Compliance/Res_48_Dark/Res_AWS-Identity-Access-Management_Permissions_48_Dark.svg",
    "kms": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Security-Identity-Compliance/64/Arch_AWS-Key-Management-Service_64.svg",
    "secrets_manager": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Security-Identity-Compliance/64/Arch_AWS-Secrets-Manager_64.svg",
    
    # Identity
    "iam_role": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Security-Identity-Compliance/64/Arch_AWS-Identity-and-Access-Management_64.svg",
    "iam_user": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Security-Identity-Compliance/64/Arch_AWS-Identity-and-Access-Management_64.svg",
    "cognito": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Security-Identity-Compliance/64/Arch_Amazon-Cognito_64.svg",
    
    # Integration
    "queue": "/aws_icons/Architecture-Service-Icons_07312025/Arch_App-Integration/64/Arch_Amazon-Simple-Queue-Service_64.svg",
    "topic": "/aws_icons/Architecture-Service-Icons_07312025/Arch_App-Integration/64/Arch_Amazon-Simple-Notification-Service_64.svg",
    "step_functions": "/aws_icons/Architecture-Service-Icons_07312025/Arch_App-Integration/64/Arch_AWS-Step-Functions_64.svg",
    
    # Monitoring
    "cloudwatch_alarm": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Management-Governance/64/Arch_Amazon-CloudWatch_64.svg",
    "cloudwatch_logs": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Management-Governance/64/Arch_Amazon-CloudWatch_64.svg",
    
    # AI
    "sagemaker": "/aws_icons/Architecture-Service-Icons_07312025/Arch_Artificial-Intelligence/64/Arch_Amazon-SageMaker_64.svg",
}

# Azure service type to icon path
AZURE_ICON_PATHS: Dict[str, str] = {
    "virtual_machine": "/Icons/compute/10021-icon-service-Virtual-Machine.svg",
    "vmss": "/Icons/compute/10034-icon-service-VM-Scale-Sets.svg",
    "app_service": "/Icons/app services/10035-icon-service-App-Services.svg",
    "app_service_plan": "/Icons/app services/00046-icon-service-App-Service-Plans.svg",
    "kubernetes": "/Icons/containers/10023-icon-service-Kubernetes-Services.svg",
    "container_instance": "/Icons/containers/10104-icon-service-Container-Instances.svg",
    "container_registry": "/Icons/containers/10105-icon-service-Container-Registries.svg",
    "storage_account": "/Icons/storage/10086-icon-service-Storage-Accounts.svg",
    "sql_server": "/Icons/databases/10132-icon-service-SQL-Server.svg",
    "sql_database": "/Icons/databases/10130-icon-service-SQL-Database.svg",
    "cosmos_db": "/Icons/databases/10121-icon-service-Azure-Cosmos-DB.svg",
    "postgresql": "/Icons/databases/10131-icon-service-Azure-Database-PostgreSQL-Server.svg",
    "mysql": "/Icons/databases/10122-icon-service-Azure-Database-MySQL-Server.svg",
    "redis_cache": "/Icons/databases/10137-icon-service-Cache-Redis.svg",
    "vnet": "/Icons/networking/10061-icon-service-Virtual-Networks.svg",
    "subnet": "/Icons/networking/02742-icon-service-Subnet.svg",
    "load_balancer": "/Icons/networking/10062-icon-service-Load-Balancers.svg",
    "app_gateway": "/Icons/networking/10076-icon-service-Application-Gateways.svg",
    "front_door": "/Icons/networking/10073-icon-service-Front-Doors.svg",
    "cdn": "/Icons/networking/00056-icon-service-CDN-Profiles.svg",
    "nsg": "/Icons/networking/10067-icon-service-Network-Security-Groups.svg",
    "public_ip": "/Icons/networking/10069-icon-service-Public-IP-Addresses.svg",
    "key_vault": "/Icons/security/10245-icon-service-Key-Vaults.svg",
    "managed_identity": "/Icons/identity/10227-icon-service-Managed-Identities.svg",
    "api_management": "/Icons/integration/10042-icon-service-API-Management-Services.svg",
    "service_bus": "/Icons/integration/10836-icon-service-Service-Bus.svg",
    "event_hub": "/Icons/integration/00039-icon-service-Event-Hubs.svg",
    "event_grid": "/Icons/integration/10221-icon-service-Event-Grid-Topics.svg",
    "logic_app": "/Icons/integration/10201-icon-service-Logic-Apps.svg",
    "function_app": "/Icons/compute/10029-icon-service-Function-Apps.svg",
    "app_insights": "/Icons/monitor/00012-icon-service-Application-Insights.svg",
    "log_analytics": "/Icons/monitor/00009-icon-service-Log-Analytics-Workspaces.svg",
    "cognitive_services": "/Icons/ai + machine learning/10162-icon-service-Cognitive-Services.svg",
    "ml_workspace": "/Icons/ai + machine learning/10167-icon-service-Machine-Learning.svg",
    "resource_group": "/Icons/management + governance/10007-icon-service-Resource-Groups.svg",
}

# GCP service type to icon path (using generic cloud icons for now)
GCP_ICON_PATHS: Dict[str, str] = {
    "virtual_machine": "/gcp_icons/compute_engine.svg",
    "kubernetes": "/gcp_icons/kubernetes_engine.svg",
    "cloud_run": "/gcp_icons/cloud_run.svg",
    "cloud_function": "/gcp_icons/cloud_functions.svg",
    "cloud_storage": "/gcp_icons/cloud_storage.svg",
    "cloud_sql": "/gcp_icons/cloud_sql.svg",
    "spanner": "/gcp_icons/cloud_spanner.svg",
    "vpc": "/gcp_icons/virtual_private_cloud.svg",
    "firestore": "/gcp_icons/firestore.svg",
}


def _get_icon_path(service_type: str, provider: CloudProvider) -> Optional[str]:
    """Get the icon path for a service type and provider."""
    if provider == CloudProvider.AWS:
        return AWS_ICON_PATHS.get(service_type)
    elif provider == CloudProvider.AZURE:
        return AZURE_ICON_PATHS.get(service_type)
    elif provider == CloudProvider.GCP:
        return GCP_ICON_PATHS.get(service_type)
    return None


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _convert_aws_tags(tags: Any) -> Dict[str, str]:
    """
    Convert AWS tags from list format to dictionary format.
    
    AWS tags can come as:
    - List of {Key: str, Value: str} objects (CloudFormation, CLI)
    - List of {key: str, value: str} objects (some APIs)
    - Already a dictionary
    
    Returns:
        Dictionary of tag key-value pairs
    """
    if tags is None:
        return {}
    if isinstance(tags, dict):
        return tags
    if isinstance(tags, list):
        result = {}
        for tag in tags:
            if isinstance(tag, dict):
                # Handle {Key: x, Value: y} format
                key = tag.get("Key") or tag.get("key") or tag.get("Name")
                value = tag.get("Value") or tag.get("value") or ""
                if key:
                    result[key] = value
        return result
    return {}


# -----------------------------------------------------------------------------
# Service Type Mappings
# -----------------------------------------------------------------------------

# Azure resource type to normalized service type
AZURE_SERVICE_TYPES: Dict[str, Tuple[str, str]] = {
    "microsoft.compute/virtualmachines": ("virtual_machine", "Compute"),
    "microsoft.compute/virtualmachinescalesets": ("vmss", "Compute"),
    "microsoft.web/sites": ("app_service", "Compute"),
    "microsoft.web/serverfarms": ("app_service_plan", "Compute"),
    "microsoft.containerservice/managedclusters": ("kubernetes", "Containers"),
    "microsoft.containerinstance/containergroups": ("container_instance", "Containers"),
    "microsoft.containerregistry/registries": ("container_registry", "Containers"),
    "microsoft.storage/storageaccounts": ("storage_account", "Storage"),
    "microsoft.sql/servers": ("sql_server", "Database"),
    "microsoft.sql/servers/databases": ("sql_database", "Database"),
    "microsoft.documentdb/databaseaccounts": ("cosmos_db", "Database"),
    "microsoft.dbforpostgresql/servers": ("postgresql", "Database"),
    "microsoft.dbformysql/servers": ("mysql", "Database"),
    "microsoft.cache/redis": ("redis_cache", "Database"),
    "microsoft.network/virtualnetworks": ("vnet", "Networking"),
    "microsoft.network/virtualnetworks/subnets": ("subnet", "Networking"),
    "microsoft.network/networkinterfaces": ("nic", "Networking"),
    "microsoft.network/publicipaddresses": ("public_ip", "Networking"),
    "microsoft.network/loadbalancers": ("load_balancer", "Networking"),
    "microsoft.network/applicationgateways": ("app_gateway", "Networking"),
    "microsoft.network/frontdoors": ("front_door", "Networking"),
    "microsoft.cdn/profiles": ("cdn", "Networking"),
    "microsoft.network/networksecuritygroups": ("nsg", "Security"),
    "microsoft.keyvault/vaults": ("key_vault", "Security"),
    "microsoft.managedidentity/userassignedidentities": ("managed_identity", "Identity"),
    "microsoft.apimanagement/service": ("api_management", "Integration"),
    "microsoft.servicebus/namespaces": ("service_bus", "Integration"),
    "microsoft.eventhub/namespaces": ("event_hub", "Integration"),
    "microsoft.eventgrid/topics": ("event_grid", "Integration"),
    "microsoft.logic/workflows": ("logic_app", "Integration"),
    "microsoft.web/sites/functions": ("function_app", "Compute"),
    "microsoft.insights/components": ("app_insights", "Monitoring"),
    "microsoft.operationalinsights/workspaces": ("log_analytics", "Monitoring"),
    "microsoft.cognitiveservices/accounts": ("cognitive_services", "AI"),
    "microsoft.machinelearningservices/workspaces": ("ml_workspace", "AI"),
}

# AWS resource type to normalized service type
AWS_SERVICE_TYPES: Dict[str, Tuple[str, str]] = {
    "aws::ec2::instance": ("virtual_machine", "Compute"),
    "aws::ec2::securitygroup": ("security_group", "Security"),
    "aws::ec2::vpc": ("vpc", "Networking"),
    "aws::ec2::subnet": ("subnet", "Networking"),
    "aws::ec2::internetgateway": ("internet_gateway", "Networking"),
    "aws::ec2::natgateway": ("nat_gateway", "Networking"),
    "aws::ec2::routetable": ("route_table", "Networking"),
    "aws::ec2::networkinterface": ("eni", "Networking"),
    "aws::elasticloadbalancingv2::loadbalancer": ("load_balancer", "Networking"),
    "aws::elasticloadbalancingv2::targetgroup": ("target_group", "Networking"),
    "aws::lambda::function": ("function", "Compute"),
    "aws::ecs::cluster": ("ecs_cluster", "Containers"),
    "aws::ecs::service": ("ecs_service", "Containers"),
    "aws::ecs::taskdefinition": ("ecs_task", "Containers"),
    "aws::eks::cluster": ("kubernetes", "Containers"),
    "aws::ecr::repository": ("container_registry", "Containers"),
    "aws::s3::bucket": ("object_storage", "Storage"),
    "aws::rds::dbinstance": ("rds", "Database"),
    "aws::rds::dbcluster": ("rds_cluster", "Database"),
    "aws::dynamodb::table": ("dynamodb", "Database"),
    "aws::elasticache::cluster": ("elasticache", "Database"),
    "aws::sqs::queue": ("queue", "Integration"),
    "aws::sns::topic": ("topic", "Integration"),
    "aws::apigateway::restapi": ("api_gateway", "Integration"),
    "aws::apigatewayv2::api": ("api_gateway_v2", "Integration"),
    "aws::stepfunctions::statemachine": ("step_functions", "Integration"),
    "aws::kms::key": ("kms", "Security"),
    "aws::secretsmanager::secret": ("secrets_manager", "Security"),
    "aws::iam::role": ("iam_role", "Identity"),
    "aws::iam::user": ("iam_user", "Identity"),
    "aws::cognito::userpool": ("cognito", "Identity"),
    "aws::cloudwatch::alarm": ("cloudwatch_alarm", "Monitoring"),
    "aws::logs::loggroup": ("cloudwatch_logs", "Monitoring"),
    "aws::cloudfront::distribution": ("cloudfront", "Networking"),
    "aws::route53::hostedzone": ("route53", "Networking"),
    "aws::sagemaker::endpoint": ("sagemaker", "AI"),
}

# GCP resource type to normalized service type
GCP_SERVICE_TYPES: Dict[str, Tuple[str, str]] = {
    "compute.googleapis.com/instance": ("virtual_machine", "Compute"),
    "compute.googleapis.com/instancetemplate": ("instance_template", "Compute"),
    "compute.googleapis.com/instancegroupmanager": ("instance_group", "Compute"),
    "compute.googleapis.com/disk": ("disk", "Storage"),
    "compute.googleapis.com/network": ("vpc", "Networking"),
    "compute.googleapis.com/subnetwork": ("subnet", "Networking"),
    "compute.googleapis.com/firewall": ("firewall", "Security"),
    "compute.googleapis.com/address": ("external_ip", "Networking"),
    "compute.googleapis.com/forwardingrule": ("load_balancer", "Networking"),
    "compute.googleapis.com/backendservice": ("backend_service", "Networking"),
    "compute.googleapis.com/urlmap": ("url_map", "Networking"),
    "container.googleapis.com/cluster": ("kubernetes", "Containers"),
    "run.googleapis.com/service": ("cloud_run", "Containers"),
    "cloudfunctions.googleapis.com/function": ("cloud_function", "Compute"),
    "storage.googleapis.com/bucket": ("cloud_storage", "Storage"),
    "sqladmin.googleapis.com/instance": ("cloud_sql", "Database"),
    "spanner.googleapis.com/instance": ("spanner", "Database"),
    "bigtable.googleapis.com/instance": ("bigtable", "Database"),
    "firestore.googleapis.com/database": ("firestore", "Database"),
    "redis.googleapis.com/instance": ("memorystore", "Database"),
    "pubsub.googleapis.com/topic": ("pubsub_topic", "Integration"),
    "pubsub.googleapis.com/subscription": ("pubsub_subscription", "Integration"),
    "cloudtasks.googleapis.com/queue": ("cloud_tasks", "Integration"),
    "secretmanager.googleapis.com/secret": ("secret_manager", "Security"),
    "cloudkms.googleapis.com/cryptokey": ("cloud_kms", "Security"),
    "iam.googleapis.com/serviceaccount": ("service_account", "Identity"),
    "monitoring.googleapis.com/alertpolicy": ("monitoring_alert", "Monitoring"),
    "logging.googleapis.com/logsink": ("logging_sink", "Monitoring"),
    "aiplatform.googleapis.com/endpoint": ("vertex_ai", "AI"),
}


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

def _generate_id() -> str:
    """Generate a unique node/edge ID."""
    return str(uuid.uuid4())[:8]


def _normalize_resource_type(raw_type: str, provider: CloudProvider) -> Tuple[str, str]:
    """
    Normalize a cloud-specific resource type to standard service_type and category.
    
    Returns (service_type, category) tuple.
    """
    normalized = raw_type.lower().strip()
    
    if provider == CloudProvider.AZURE:
        mapping = AZURE_SERVICE_TYPES.get(normalized)
        if mapping:
            return mapping
        # Try partial match for nested resources
        for key, value in AZURE_SERVICE_TYPES.items():
            if key in normalized or normalized in key:
                return value
                
    elif provider == CloudProvider.AWS:
        mapping = AWS_SERVICE_TYPES.get(normalized)
        if mapping:
            return mapping
        # AWS CloudFormation format: AWS::Service::Resource
        for key, value in AWS_SERVICE_TYPES.items():
            if key in normalized or normalized in key:
                return value
                
    elif provider == CloudProvider.GCP:
        mapping = GCP_SERVICE_TYPES.get(normalized)
        if mapping:
            return mapping
        for key, value in GCP_SERVICE_TYPES.items():
            if key in normalized or normalized in key:
                return value
    
    # Fallback: derive from resource type
    parts = re.split(r'[/:.]+', normalized)
    service_type = parts[-1] if parts else "unknown"
    category = "Other"
    
    return service_type, category


def _extract_region(resource: Dict[str, Any], provider: CloudProvider) -> Optional[str]:
    """Extract region/location from resource data."""
    # Common location field names
    location_fields = ["location", "region", "availabilityZone", "zone"]
    
    for field in location_fields:
        if field in resource:
            return str(resource[field])
        # Check nested in properties
        props = resource.get("properties", {})
        if isinstance(props, dict) and field in props:
            return str(props[field])
    
    return None


def _extract_parent_id(resource: Dict[str, Any], provider: CloudProvider) -> Optional[str]:
    """Extract parent resource ID for hierarchy."""
    if provider == CloudProvider.AZURE:
        # Azure uses resource ID hierarchy
        resource_id = resource.get("id", "")
        if "/" in resource_id:
            # Extract resource group as parent
            rg_match = re.search(r'/resourceGroups/([^/]+)', resource_id, re.IGNORECASE)
            if rg_match:
                return f"rg-{rg_match.group(1).lower()}"
                
    elif provider == CloudProvider.AWS:
        # AWS uses VPC as parent for networking resources
        vpc_id = resource.get("vpcId") or resource.get("VpcId")
        if vpc_id:
            return vpc_id
            
    elif provider == CloudProvider.GCP:
        # GCP uses project/network hierarchy
        network = resource.get("network")
        if network:
            # Extract network name from full path
            parts = network.split("/")
            return parts[-1] if parts else None
    
    return None


def _infer_edges(nodes: List[InfraNode], provider: CloudProvider) -> List[InfraEdge]:
    """
    Infer edges between nodes based on common patterns.
    
    This is a heuristic approach that detects:
    - Parent-child containment relationships
    - Network dependencies (same VNet/VPC)
    - Service dependencies from properties
    """
    edges: List[InfraEdge] = []
    node_by_id = {n.id: n for n in nodes}
    
    for node in nodes:
        # Containment edges from parent_id
        if node.parent_id and node.parent_id in node_by_id:
            edges.append(InfraEdge(
                id=f"edge-{_generate_id()}",
                source=node.parent_id,
                target=node.id,
                source_handle=None,
                target_handle=None,
                edge_type=EdgeType.CONTAINS,
                label="contains"
            ))
        
        # Network edges: resources in same subnet/VNet
        node_subnet = node.properties.get("subnet_id") or node.properties.get("subnetId")
        if node_subnet:
            for other in nodes:
                if other.id != node.id:
                    other_subnet = other.properties.get("subnet_id") or other.properties.get("subnetId")
                    if node_subnet == other_subnet:
                        # Avoid duplicates - only create edge in one direction
                        if node.id < other.id:
                            edges.append(InfraEdge(
                                id=f"edge-{_generate_id()}",
                                source=node.id,
                                target=other.id,
                                source_handle=None,
                                target_handle=None,
                                edge_type=EdgeType.NETWORK,
                                label="same subnet"
                            ))
        
        # Data dependencies: storage account references
        storage_ref = node.properties.get("storageAccountId") or node.properties.get("storage_account")
        if storage_ref:
            for other in nodes:
                if other.service_type in ("storage_account", "object_storage", "cloud_storage"):
                    if storage_ref in (other.id, other.resource_id, other.properties.get("name")):
                        edges.append(InfraEdge(
                            id=f"edge-{_generate_id()}",
                            source=node.id,
                            target=other.id,
                            source_handle=None,
                            target_handle=None,
                            edge_type=EdgeType.DATA,
                            label="uses storage"
                        ))
        
        # Database dependencies
        db_ref = (
            node.properties.get("databaseId") or 
            node.properties.get("database") or
            node.properties.get("connectionString")
        )
        if db_ref:
            for other in nodes:
                if other.category == "Database":
                    if isinstance(db_ref, str) and (other.id in db_ref or other.label.lower() in db_ref.lower()):
                        edges.append(InfraEdge(
                            id=f"edge-{_generate_id()}",
                            source=node.id,
                            target=other.id,
                            source_handle=None,
                            target_handle=None,
                            edge_type=EdgeType.DATA,
                            label="database connection"
                        ))
    
    # Deduplicate edges
    seen = set()
    unique_edges = []
    for edge in edges:
        key = (edge.source, edge.target, edge.edge_type)
        if key not in seen:
            seen.add(key)
            unique_edges.append(edge)
    
    return unique_edges


# -----------------------------------------------------------------------------
# Azure Parser
# -----------------------------------------------------------------------------

def normalize_azure(raw_inventory: Dict[str, Any]) -> InfraGraph:
    """
    Parse Azure resource inventory into InfraGraph.
    
    Supports formats:
    - Azure Resource Graph query results
    - ARM template resources array
    - Azure CLI resource list output
    
    Args:
        raw_inventory: Raw Azure inventory JSON
        
    Returns:
        InfraGraph with normalized nodes and inferred edges
    """
    nodes: List[InfraNode] = []
    resource_groups: Dict[str, InfraNode] = {}
    
    # Detect format and extract resources array
    resources = []
    if "resources" in raw_inventory:
        resources = raw_inventory["resources"]
    elif "value" in raw_inventory:
        resources = raw_inventory["value"]
    elif "data" in raw_inventory:
        resources = raw_inventory["data"]
    elif isinstance(raw_inventory, list):
        resources = raw_inventory
    else:
        # Single resource
        resources = [raw_inventory]
    
    logger.info(f"Parsing {len(resources)} Azure resources")
    
    for resource in resources:
        if not isinstance(resource, dict):
            continue
            
        # Extract resource type
        resource_type = resource.get("type", "")
        if not resource_type:
            continue
        
        # Normalize service type
        service_type, category = _normalize_resource_type(resource_type, CloudProvider.AZURE)
        
        # Extract resource group for hierarchy
        resource_id = resource.get("id", "")
        rg_name = None
        rg_match = re.search(r'/resourceGroups/([^/]+)', resource_id, re.IGNORECASE)
        if rg_match:
            rg_name = rg_match.group(1)
            # Create resource group node if not exists
            rg_node_id = f"rg-{rg_name.lower()}"
            if rg_node_id not in resource_groups:
                rg_node = InfraNode(
                    id=rg_node_id,
                    provider=CloudProvider.AZURE,
                    service_type="resource_group",
                    label=rg_name,
                    resource_id=None,
                    resource_type="Microsoft.Resources/resourceGroups",
                    parent_id=None,
                    region=resource.get("location"),
                    tags={},
                    properties={"name": rg_name},
                    icon_path=_get_icon_path("resource_group", CloudProvider.AZURE),
                    category="Management",
                    raw_data=None
                )
                resource_groups[rg_node_id] = rg_node
        
        # Build node properties
        properties: Dict[str, Any] = {}
        if "properties" in resource and isinstance(resource["properties"], dict):
            properties = resource["properties"].copy()
        if "sku" in resource:
            properties["sku"] = resource["sku"]
        if "kind" in resource:
            properties["kind"] = resource["kind"]
        
        # Create node
        node = InfraNode(
            id=resource.get("name", _generate_id()),
            provider=CloudProvider.AZURE,
            service_type=service_type,
            label=resource.get("name", service_type),
            resource_id=resource_id,
            resource_type=resource_type,
            parent_id=f"rg-{rg_name.lower()}" if rg_name else None,
            region=resource.get("location"),
            tags=resource.get("tags", {}),
            properties=properties,
            icon_path=_get_icon_path(service_type, CloudProvider.AZURE),
            category=category,
            raw_data=resource
        )
        nodes.append(node)
    
    # Add resource group nodes
    nodes = list(resource_groups.values()) + nodes
    
    # Infer edges
    edges = _infer_edges(nodes, CloudProvider.AZURE)
    
    logger.info(f"Created {len(nodes)} nodes and {len(edges)} edges from Azure inventory")
    return InfraGraph(
        provider=CloudProvider.AZURE,
        nodes=nodes,
        edges=edges,
        source="azure_import",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        metadata={"original_count": len(resources)}
    )


# -----------------------------------------------------------------------------
# AWS Parser
# -----------------------------------------------------------------------------

def normalize_aws(raw_inventory: Dict[str, Any]) -> InfraGraph:
    """
    Parse AWS resource inventory into InfraGraph.
    
    Supports formats:
    - AWS Config resource list
    - CloudFormation template resources
    - AWS Resource Explorer results
    - AWS CLI describe-* output
    
    Args:
        raw_inventory: Raw AWS inventory JSON
        
    Returns:
        InfraGraph with normalized nodes and inferred edges
    """
    nodes: List[InfraNode] = []
    vpcs: Dict[str, InfraNode] = {}
    
    # Detect format and extract resources
    resources = []
    if "Resources" in raw_inventory:
        # CloudFormation format
        cf_resources = raw_inventory["Resources"]
        for logical_id, resource_def in cf_resources.items():
            resource_def["LogicalId"] = logical_id
            resources.append(resource_def)
    elif "resources" in raw_inventory:
        resources = raw_inventory["resources"]
    elif "ResourceIdentifiers" in raw_inventory:
        # AWS Resource Explorer format
        resources = raw_inventory["ResourceIdentifiers"]
    elif isinstance(raw_inventory, list):
        resources = raw_inventory
    else:
        resources = [raw_inventory]
    
    logger.info(f"Parsing {len(resources)} AWS resources")
    
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        
        # Extract resource type (handle different formats)
        resource_type = (
            resource.get("Type") or 
            resource.get("resourceType") or 
            resource.get("ResourceType") or
            ""
        )
        if not resource_type:
            continue
        
        # Normalize to AWS::Service::Resource format
        if not resource_type.startswith("AWS::") and not resource_type.startswith("aws::"):
            resource_type = f"AWS::{resource_type}"
        
        service_type, category = _normalize_resource_type(resource_type.lower(), CloudProvider.AWS)
        
        # Extract properties
        properties: Dict[str, Any] = {}
        if "Properties" in resource:
            properties = resource["Properties"].copy()
        elif "configuration" in resource:
            properties = resource["configuration"].copy()
        
        # Handle VPC hierarchy
        vpc_id = properties.get("VpcId") or properties.get("vpcId")
        if vpc_id and vpc_id not in vpcs:
            vpc_node = InfraNode(
                id=vpc_id,
                provider=CloudProvider.AWS,
                service_type="vpc",
                label=f"VPC {vpc_id}",
                resource_id=vpc_id,
                resource_type="AWS::EC2::VPC",
                parent_id=None,
                region=None,
                tags={},
                properties={"vpcId": vpc_id},
                icon_path=_get_icon_path("vpc", CloudProvider.AWS),
                category="Networking",
                raw_data=None
            )
            vpcs[vpc_id] = vpc_node
        
        # Generate node ID
        node_id = (
            resource.get("LogicalId") or
            resource.get("resourceId") or
            resource.get("Arn", "").split("/")[-1] or
            properties.get("Name") or
            _generate_id()
        )
        
        # Extract name
        name = (
            properties.get("Name") or
            properties.get("FunctionName") or
            properties.get("BucketName") or
            properties.get("TableName") or
            properties.get("ClusterName") or
            node_id
        )
        
        # Extract region from ARN if present
        region = None
        arn = resource.get("Arn") or resource.get("arn")
        if arn:
            arn_parts = arn.split(":")
            if len(arn_parts) >= 4:
                region = arn_parts[3]
        
        # Convert tags from AWS list format to dictionary
        raw_tags = properties.get("Tags") or resource.get("Tags") or resource.get("tags") or {}
        tags = _convert_aws_tags(raw_tags)
        
        # Create node
        node = InfraNode(
            id=node_id,
            provider=CloudProvider.AWS,
            service_type=service_type,
            label=name,
            resource_id=arn or resource.get("resourceId"),
            resource_type=resource_type,
            parent_id=vpc_id,
            region=region,
            tags=tags,
            properties=properties,
            icon_path=_get_icon_path(service_type, CloudProvider.AWS),
            category=category,
            raw_data=resource
        )
        nodes.append(node)
    
    # Add VPC nodes
    nodes = list(vpcs.values()) + nodes
    
    # Infer edges
    edges = _infer_edges(nodes, CloudProvider.AWS)
    return InfraGraph(
        provider=CloudProvider.AWS,
        nodes=nodes,
        edges=edges,
        source="aws_import",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        metadata={"original_count": len(resources)}
    )


# -----------------------------------------------------------------------------
# GCP Parser
# -----------------------------------------------------------------------------

def normalize_gcp(raw_inventory: Dict[str, Any]) -> InfraGraph:
    """
    Parse GCP resource inventory into InfraGraph.
    
    Supports formats:
    - Cloud Asset Inventory export
    - Deployment Manager resources
    - gcloud CLI output
    
    Args:
        raw_inventory: Raw GCP inventory JSON
        
    Returns:
        InfraGraph with normalized nodes and inferred edges
    """
    nodes: List[InfraNode] = []
    networks: Dict[str, InfraNode] = {}
    
    # Detect format and extract resources
    resources = []
    if "assets" in raw_inventory:
        # Cloud Asset Inventory format
        resources = raw_inventory["assets"]
    elif "resources" in raw_inventory:
        resources = raw_inventory["resources"]
    elif isinstance(raw_inventory, list):
        resources = raw_inventory
    else:
        resources = [raw_inventory]
    
    logger.info(f"Parsing {len(resources)} GCP resources")
    
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        
        # Extract resource type
        resource_type = (
            resource.get("assetType") or
            resource.get("type") or
            ""
        )
        if not resource_type:
            continue
        
        service_type, category = _normalize_resource_type(resource_type, CloudProvider.GCP)
        
        # Extract properties from nested resource structure
        properties: Dict[str, Any] = {}
        resource_data = resource.get("resource", {}).get("data", {})
        if resource_data:
            properties = resource_data.copy()
        elif "properties" in resource:
            properties = resource["properties"].copy()
        
        # Handle network hierarchy
        network_ref = properties.get("network") or properties.get("networkRef")
        if network_ref:
            network_name = network_ref.split("/")[-1] if "/" in network_ref else network_ref
            if network_name not in networks:
                network_node = InfraNode(
                    id=network_name,
                    provider=CloudProvider.GCP,
                    service_type="vpc",
                    label=f"VPC {network_name}",
                    resource_id=None,
                    resource_type="compute.googleapis.com/Network",
                    parent_id=None,
                    region=None,
                    tags={},
                    properties={"name": network_name},
                    icon_path=None,
                    category="Networking",
                    raw_data=None
                )
                networks[network_name] = network_node
        
        # Generate node ID
        name = (
            resource.get("name") or
            properties.get("name") or
            resource.get("displayName") or
            _generate_id()
        )
        
        # Extract region/zone
        region = None
        zone = properties.get("zone") or resource.get("zone")
        if zone:
            # Extract region from zone (e.g., us-central1-a -> us-central1)
            region = "-".join(zone.split("-")[:-1]) if "-" in zone else zone
        else:
            region = properties.get("region") or properties.get("location")
        
        # Extract self link as resource ID
        resource_id = (
            resource.get("name") or
            properties.get("selfLink") or
            resource.get("resource", {}).get("location")
        )
        
        # Create node
        node = InfraNode(
            id=name,
            provider=CloudProvider.GCP,
            service_type=service_type,
            label=name,
            resource_id=resource_id,
            resource_type=resource_type,
            parent_id=network_ref.split("/")[-1] if network_ref else None,
            region=region,
            tags=properties.get("labels", {}),
            properties=properties,
            icon_path=None,
            category=category,
            raw_data=resource
        )
        nodes.append(node)
    
    # Add network nodes
    nodes = list(networks.values()) + nodes
    
    # Infer edges
    edges = _infer_edges(nodes, CloudProvider.GCP)
    
    logger.info(f"Created {len(nodes)} nodes and {len(edges)} edges from GCP inventory")
    return InfraGraph(
        provider=CloudProvider.GCP,
        nodes=nodes,
        edges=edges,
        source="gcp_import",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        metadata={"original_count": len(resources)}
    )


# -----------------------------------------------------------------------------
# Auto-Detection and Unified Parser
# -----------------------------------------------------------------------------

def detect_provider(raw_inventory: Any) -> Optional[CloudProvider]:
    """
    Auto-detect cloud provider from inventory structure.
    
    Returns:
        CloudProvider or None if cannot determine
    """
    # Check for Azure patterns
    if "value" in raw_inventory:
        # Azure Resource Graph format
        first = raw_inventory["value"][0] if raw_inventory["value"] else {}
        if isinstance(first, dict) and "type" in first:
            resource_type = first["type"].lower()
            if resource_type.startswith("microsoft."):
                return CloudProvider.AZURE
    
    if "resources" in raw_inventory:
        resources = raw_inventory["resources"]
        if resources and isinstance(resources[0], dict):
            first = resources[0]
            # Check for Azure resource type
            if "type" in first:
                rt = first["type"].lower()
                if rt.startswith("microsoft."):
                    return CloudProvider.AZURE
            # Check for GCP asset type
            if "assetType" in first:
                return CloudProvider.GCP
    
    # Check for AWS patterns
    if "Resources" in raw_inventory:
        # CloudFormation format
        for resource in raw_inventory["Resources"].values():
            if "Type" in resource:
                rt = resource["Type"]
                if rt.startswith("AWS::"):
                    return CloudProvider.AWS
    
    if "ResourceIdentifiers" in raw_inventory:
        return CloudProvider.AWS
    
    # Check for GCP patterns
    if "assets" in raw_inventory:
        return CloudProvider.GCP
    
    # Check list format
    if isinstance(raw_inventory, list) and raw_inventory:
        first = raw_inventory[0]
        if isinstance(first, dict):
            if "type" in first:
                rt = first["type"].lower()
                if rt.startswith("microsoft."):
                    return CloudProvider.AZURE
                elif rt.startswith("aws::"):
                    return CloudProvider.AWS
            if "assetType" in first:
                return CloudProvider.GCP
    
    return None


def parse_inventory(
    raw_inventory: Dict[str, Any],
    provider: Optional[CloudProvider] = None
) -> InfraGraph:
    """
    Parse cloud inventory with auto-detection.
    
    Args:
        raw_inventory: Raw cloud inventory JSON
        provider: Optional provider hint (auto-detects if None)
        
    Returns:
        InfraGraph with normalized nodes and edges
        
    Raises:
        ValueError: If provider cannot be determined
    """
    if provider is None:
        provider = detect_provider(raw_inventory)
    
    if provider is None:
        raise ValueError(
            "Cannot determine cloud provider from inventory format. "
            "Please specify provider explicitly."
        )
    
    if provider == CloudProvider.AZURE:
        return normalize_azure(raw_inventory)
    elif provider == CloudProvider.AWS:
        return normalize_aws(raw_inventory)
    elif provider == CloudProvider.GCP:
        return normalize_gcp(raw_inventory)
    else:
        raise ValueError(f"Unsupported provider: {provider}")
