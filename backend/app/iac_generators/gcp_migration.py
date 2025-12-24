"""
Utilities for migrating GCP-native diagrams into Azure-native representations.

The migration routine keeps the original node metadata for traceability,
remaps the titles/resource types to Azure equivalents, and attaches
lightweight price comparisons plus canned Bicep snippets that can be surfaced
in the UI or downstream reports.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


@dataclass
class GcpMigrationResult:
    """Structured result of a GCP migration pass."""

    diagram: Dict[str, Any]
    converted_nodes: List[Dict[str, Any]] = field(default_factory=list)
    price_summary: List[Dict[str, Any]] = field(default_factory=list)
    cost_summary: Dict[str, Any] = field(default_factory=dict)
    bicep_snippets: List[Dict[str, Any]] = field(default_factory=list)
    unmapped_services: List[Dict[str, Any]] = field(default_factory=list)
    applied: bool = False


def _normalize(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _bicep_vm_snippet() -> str:
    return """@description('Virtual machine that replaces the GCP Compute Engine instance')
param location string = resourceGroup().location
param vmName string = 'vm-${uniqueString(resourceGroup().id)}'

resource vm 'Microsoft.Compute/virtualMachines@2023-09-01' = {
  name: vmName
  location: location
  properties: {
    hardwareProfile: {
      vmSize: 'Standard_B2s'
    }
    storageProfile: {
      imageReference: {
        publisher: 'Canonical'
        offer: '0001-com-ubuntu-server-jammy'
        sku: '22_04-lts'
        version: 'latest'
      }
      osDisk: {
        createOption: 'FromImage'
        managedDisk: {
          storageAccountType: 'Premium_LRS'
        }
      }
    }
    osProfile: {
      computerName: vmName
      adminUsername: 'azureuser'
      adminPassword: 'P@ssw0rd1234!'
    }
    networkProfile: {
      networkInterfaces: []
    }
  }
}
"""


def _bicep_functions_snippet() -> str:
    return """@description('Azure Function replacing GCP Cloud Functions')
param location string = resourceGroup().location
param storageAccountName string
param functionAppName string = 'fn-${uniqueString(resourceGroup().id)}'

resource functionPlan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: 'consumption-plan'
  location: location
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  kind: 'functionapp'
}

resource functionApp 'Microsoft.Web/sites@2022-09-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp'
  properties: {
    serverFarmId: functionPlan.id
    httpsOnly: true
    siteConfig: {
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName}'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'node'
        }
      ]
    }
  }
}
"""


def _bicep_storage_snippet() -> str:
    return """@description('Azure Storage Account replacing GCP Cloud Storage')
param location string = resourceGroup().location
param storageAccountName string = 'st${uniqueString(resourceGroup().id)}'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
}
"""


def _bicep_sql_snippet() -> str:
    return """@description('Azure SQL Database replacing GCP Cloud SQL')
param location string = resourceGroup().location
param sqlServerName string = 'sql-${uniqueString(resourceGroup().id)}'
param databaseName string = 'sqldb-main'

resource sqlServer 'Microsoft.Sql/servers@2023-05-01-preview' = {
  name: sqlServerName
  location: location
  properties: {
    administratorLogin: 'sqladmin'
    administratorLoginPassword: 'P@ssw0rd1234!'
    version: '12.0'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-05-01-preview' = {
  parent: sqlServer
  name: databaseName
  location: location
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
}
"""


def _bicep_cosmos_snippet() -> str:
    return """@description('Azure Cosmos DB replacing GCP Firestore/Datastore')
param location string = resourceGroup().location
param cosmosAccountName string = 'cosmos-${uniqueString(resourceGroup().id)}'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: cosmosAccountName
  location: location
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
  }
}
"""


def _bicep_aks_snippet() -> str:
    return """@description('Azure Kubernetes Service replacing GCP GKE')
param location string = resourceGroup().location
param aksClusterName string = 'aks-${uniqueString(resourceGroup().id)}'

resource aksCluster 'Microsoft.ContainerService/managedClusters@2023-11-01' = {
  name: aksClusterName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    dnsPrefix: aksClusterName
    agentPoolProfiles: [
      {
        name: 'nodepool1'
        count: 3
        vmSize: 'Standard_D2s_v3'
        mode: 'System'
      }
    ]
  }
}
"""


def _bicep_pubsub_snippet() -> str:
    return """@description('Azure Service Bus replacing GCP Pub/Sub')
param location string = resourceGroup().location
param serviceBusName string = 'sb-${uniqueString(resourceGroup().id)}'

resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: serviceBusName
  location: location
  sku: {
    name: 'Standard'
  }
}

resource topic 'Microsoft.ServiceBus/namespaces/topics@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: 'messages'
}
"""


def _bicep_redis_snippet() -> str:
    return """@description('Azure Cache for Redis replacing GCP Memorystore')
param location string = resourceGroup().location
param redisName string = 'redis-${uniqueString(resourceGroup().id)}'

resource redisCache 'Microsoft.Cache/redis@2023-08-01' = {
  name: redisName
  location: location
  properties: {
    sku: {
      name: 'Basic'
      family: 'C'
      capacity: 0
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
  }
}
"""


def _build_cost_summary(price_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate monthly cost totals and compute deltas."""
    gcp_total = 0.0
    azure_total = 0.0
    currency = "USD"

    for row in price_rows:
        gcp_val = row.get("gcp_monthly")
        azure_val = row.get("azure_monthly")
        if isinstance(gcp_val, (int, float)):
            gcp_total += gcp_val
        if isinstance(azure_val, (int, float)):
            azure_total += azure_val
        if row.get("currency"):
            currency = row["currency"]

    delta = azure_total - gcp_total
    savings_pct = 0.0
    if gcp_total > 0:
        savings_pct = (delta / gcp_total) * 100

    verdict = "Comparable costs"
    if delta < -10:
        verdict = "Azure is more cost-effective"
    elif delta > 10:
        verdict = "GCP is more cost-effective"

    return {
        "gcp_monthly_total": round(gcp_total, 2),
        "azure_monthly_total": round(azure_total, 2),
        "delta": round(delta, 2),
        "savings_percent": round(savings_pct, 2),
        "currency": currency,
        "verdict": verdict,
    }


# Comprehensive GCP to Azure service mappings
GCP_TO_AZURE_MAPPINGS = {
    # Compute
    "compute engine": {
        "azure_service": "Virtual Machine",
        "azure_category": "Compute",
        "azure_resource_type": "Microsoft.Compute/virtualMachines",
        "description": "VM instances for compute workloads",
        "cost": {"gcp_monthly": 25, "azure_monthly": 30, "currency": "USD", "assumptions": "e2-medium vs Standard_B2s"},
        "bicep_template": _bicep_vm_snippet(),
    },
    "gce": {
        "azure_service": "Virtual Machine",
        "azure_category": "Compute",
        "azure_resource_type": "Microsoft.Compute/virtualMachines",
        "description": "VM instances for compute workloads",
        "cost": {"gcp_monthly": 25, "azure_monthly": 30, "currency": "USD", "assumptions": "e2-medium vs Standard_B2s"},
        "bicep_template": _bicep_vm_snippet(),
    },
    "app engine": {
        "azure_service": "App Service",
        "azure_category": "Compute",
        "azure_resource_type": "Microsoft.Web/sites",
        "description": "Platform for building web apps",
        "cost": {"gcp_monthly": 55, "azure_monthly": 55, "currency": "USD", "assumptions": "Standard tier equivalent"},
    },
    "cloud functions": {
        "azure_service": "Azure Functions",
        "azure_category": "Compute",
        "azure_resource_type": "Microsoft.Web/sites",
        "description": "Serverless compute functions",
        "cost": {"gcp_monthly": 0.40, "azure_monthly": 0.20, "currency": "USD", "assumptions": "1M executions/month"},
        "bicep_template": _bicep_functions_snippet(),
    },
    "cloud run": {
        "azure_service": "Container Apps",
        "azure_category": "Containers",
        "azure_resource_type": "Microsoft.App/containerApps",
        "description": "Serverless container platform",
        "cost": {"gcp_monthly": 10, "azure_monthly": 12, "currency": "USD", "assumptions": "Consumption tier"},
    },
    
    # Storage
    "cloud storage": {
        "azure_service": "Azure Storage (Blob)",
        "azure_category": "Storage",
        "azure_resource_type": "Microsoft.Storage/storageAccounts",
        "description": "Object storage service",
        "cost": {"gcp_monthly": 20, "azure_monthly": 18, "currency": "USD", "assumptions": "Standard LRS, 1TB"},
        "bicep_template": _bicep_storage_snippet(),
    },
    "gcs": {
        "azure_service": "Azure Storage (Blob)",
        "azure_category": "Storage",
        "azure_resource_type": "Microsoft.Storage/storageAccounts",
        "description": "Object storage service",
        "cost": {"gcp_monthly": 20, "azure_monthly": 18, "currency": "USD", "assumptions": "Standard LRS, 1TB"},
        "bicep_template": _bicep_storage_snippet(),
    },
    "persistent disk": {
        "azure_service": "Managed Disks",
        "azure_category": "Storage",
        "azure_resource_type": "Microsoft.Compute/disks",
        "description": "Block storage for VMs",
        "cost": {"gcp_monthly": 40, "azure_monthly": 38, "currency": "USD", "assumptions": "Premium SSD 512GB"},
    },
    "filestore": {
        "azure_service": "Azure Files",
        "azure_category": "Storage",
        "azure_resource_type": "Microsoft.Storage/storageAccounts/fileServices",
        "description": "Managed file shares",
        "cost": {"gcp_monthly": 200, "azure_monthly": 180, "currency": "USD", "assumptions": "1TB Premium tier"},
    },
    
    # Databases
    "cloud sql": {
        "azure_service": "Azure SQL Database",
        "azure_category": "Databases",
        "azure_resource_type": "Microsoft.Sql/servers/databases",
        "description": "Managed relational database",
        "cost": {"gcp_monthly": 45, "azure_monthly": 50, "currency": "USD", "assumptions": "db-n1-standard-1 vs S1"},
        "bicep_template": _bicep_sql_snippet(),
    },
    "cloud spanner": {
        "azure_service": "Azure Cosmos DB",
        "azure_category": "Databases",
        "azure_resource_type": "Microsoft.DocumentDB/databaseAccounts",
        "description": "Globally distributed database",
        "cost": {"gcp_monthly": 900, "azure_monthly": 700, "currency": "USD", "assumptions": "Multi-region, 1000 RU/s"},
        "bicep_template": _bicep_cosmos_snippet(),
    },
    "firestore": {
        "azure_service": "Azure Cosmos DB",
        "azure_category": "Databases",
        "azure_resource_type": "Microsoft.DocumentDB/databaseAccounts",
        "description": "NoSQL document database",
        "cost": {"gcp_monthly": 50, "azure_monthly": 45, "currency": "USD", "assumptions": "Native mode, 1000 RU/s"},
        "bicep_template": _bicep_cosmos_snippet(),
    },
    "datastore": {
        "azure_service": "Azure Cosmos DB",
        "azure_category": "Databases",
        "azure_resource_type": "Microsoft.DocumentDB/databaseAccounts",
        "description": "NoSQL database service",
        "cost": {"gcp_monthly": 50, "azure_monthly": 45, "currency": "USD", "assumptions": "1000 RU/s"},
        "bicep_template": _bicep_cosmos_snippet(),
    },
    "bigtable": {
        "azure_service": "Azure Cosmos DB (Table API)",
        "azure_category": "Databases",
        "azure_resource_type": "Microsoft.DocumentDB/databaseAccounts",
        "description": "NoSQL wide-column database",
        "cost": {"gcp_monthly": 350, "azure_monthly": 300, "currency": "USD", "assumptions": "3 nodes cluster"},
    },
    "bigquery": {
        "azure_service": "Azure Synapse Analytics",
        "azure_category": "Analytics",
        "azure_resource_type": "Microsoft.Synapse/workspaces",
        "description": "Data warehouse and analytics",
        "cost": {"gcp_monthly": 200, "azure_monthly": 220, "currency": "USD", "assumptions": "1TB queries/month"},
    },
    "memorystore": {
        "azure_service": "Azure Cache for Redis",
        "azure_category": "Databases",
        "azure_resource_type": "Microsoft.Cache/redis",
        "description": "In-memory data store",
        "cost": {"gcp_monthly": 45, "azure_monthly": 40, "currency": "USD", "assumptions": "Basic tier 1GB"},
        "bicep_template": _bicep_redis_snippet(),
    },
    
    # Containers & Kubernetes
    "google kubernetes engine": {
        "azure_service": "Azure Kubernetes Service",
        "azure_category": "Containers",
        "azure_resource_type": "Microsoft.ContainerService/managedClusters",
        "description": "Managed Kubernetes clusters",
        "cost": {"gcp_monthly": 75, "azure_monthly": 0, "currency": "USD", "assumptions": "Cluster management free on Azure"},
        "bicep_template": _bicep_aks_snippet(),
    },
    "gke": {
        "azure_service": "Azure Kubernetes Service",
        "azure_category": "Containers",
        "azure_resource_type": "Microsoft.ContainerService/managedClusters",
        "description": "Managed Kubernetes clusters",
        "cost": {"gcp_monthly": 75, "azure_monthly": 0, "currency": "USD", "assumptions": "Cluster management free on Azure"},
        "bicep_template": _bicep_aks_snippet(),
    },
    "container registry": {
        "azure_service": "Azure Container Registry",
        "azure_category": "Containers",
        "azure_resource_type": "Microsoft.ContainerRegistry/registries",
        "description": "Private container registry",
        "cost": {"gcp_monthly": 5, "azure_monthly": 5, "currency": "USD", "assumptions": "Basic tier, 10GB storage"},
    },
    
    # Networking
    "cloud vpc": {
        "azure_service": "Virtual Network",
        "azure_category": "Networking",
        "azure_resource_type": "Microsoft.Network/virtualNetworks",
        "description": "Private network infrastructure",
        "cost": {"gcp_monthly": 0, "azure_monthly": 0, "currency": "USD", "assumptions": "No charge for VNet itself"},
    },
    "vpc": {
        "azure_service": "Virtual Network",
        "azure_category": "Networking",
        "azure_resource_type": "Microsoft.Network/virtualNetworks",
        "description": "Private network infrastructure",
        "cost": {"gcp_monthly": 0, "azure_monthly": 0, "currency": "USD", "assumptions": "No charge for VNet itself"},
    },
    "cloud load balancing": {
        "azure_service": "Azure Load Balancer",
        "azure_category": "Networking",
        "azure_resource_type": "Microsoft.Network/loadBalancers",
        "description": "Layer 4 load balancing",
        "cost": {"gcp_monthly": 18, "azure_monthly": 20, "currency": "USD", "assumptions": "Standard tier"},
    },
    "cloud cdn": {
        "azure_service": "Azure CDN",
        "azure_category": "Networking",
        "azure_resource_type": "Microsoft.Cdn/profiles",
        "description": "Content delivery network",
        "cost": {"gcp_monthly": 80, "azure_monthly": 75, "currency": "USD", "assumptions": "1TB data transfer"},
    },
    "cloud dns": {
        "azure_service": "Azure DNS",
        "azure_category": "Networking",
        "azure_resource_type": "Microsoft.Network/dnsZones",
        "description": "Domain name system service",
        "cost": {"gcp_monthly": 2, "azure_monthly": 2, "currency": "USD", "assumptions": "1 million queries"},
    },
    "cloud nat": {
        "azure_service": "NAT Gateway",
        "azure_category": "Networking",
        "azure_resource_type": "Microsoft.Network/natGateways",
        "description": "Network address translation",
        "cost": {"gcp_monthly": 45, "azure_monthly": 45, "currency": "USD", "assumptions": "Similar pricing"},
    },
    
    # Messaging & Integration
    "pub sub": {
        "azure_service": "Azure Service Bus",
        "azure_category": "Integration",
        "azure_resource_type": "Microsoft.ServiceBus/namespaces",
        "description": "Message queue and pub/sub",
        "cost": {"gcp_monthly": 40, "azure_monthly": 35, "currency": "USD", "assumptions": "Standard tier"},
        "bicep_template": _bicep_pubsub_snippet(),
    },
    "pubsub": {
        "azure_service": "Azure Service Bus",
        "azure_category": "Integration",
        "azure_resource_type": "Microsoft.ServiceBus/namespaces",
        "description": "Message queue and pub/sub",
        "cost": {"gcp_monthly": 40, "azure_monthly": 35, "currency": "USD", "assumptions": "Standard tier"},
        "bicep_template": _bicep_pubsub_snippet(),
    },
    "cloud tasks": {
        "azure_service": "Azure Queue Storage",
        "azure_category": "Integration",
        "azure_resource_type": "Microsoft.Storage/storageAccounts/queueServices",
        "description": "Task queue service",
        "cost": {"gcp_monthly": 5, "azure_monthly": 3, "currency": "USD", "assumptions": "1M operations"},
    },
    
    # AI & ML
    "vertex ai": {
        "azure_service": "Azure Machine Learning",
        "azure_category": "AI + Machine Learning",
        "azure_resource_type": "Microsoft.MachineLearningServices/workspaces",
        "description": "ML platform and model training",
        "cost": {"gcp_monthly": 300, "azure_monthly": 280, "currency": "USD", "assumptions": "Basic compute instances"},
    },
    "ai platform": {
        "azure_service": "Azure Machine Learning",
        "azure_category": "AI + Machine Learning",
        "azure_resource_type": "Microsoft.MachineLearningServices/workspaces",
        "description": "ML platform and model training",
        "cost": {"gcp_monthly": 300, "azure_monthly": 280, "currency": "USD", "assumptions": "Basic compute instances"},
    },
    "vision api": {
        "azure_service": "Computer Vision",
        "azure_category": "AI + Machine Learning",
        "azure_resource_type": "Microsoft.CognitiveServices/accounts",
        "description": "Image analysis and OCR",
        "cost": {"gcp_monthly": 15, "azure_monthly": 10, "currency": "USD", "assumptions": "10K transactions"},
    },
    "natural language api": {
        "azure_service": "Language Service",
        "azure_category": "AI + Machine Learning",
        "azure_resource_type": "Microsoft.CognitiveServices/accounts",
        "description": "Text analytics and NLP",
        "cost": {"gcp_monthly": 20, "azure_monthly": 15, "currency": "USD", "assumptions": "10K records"},
    },
    "speech to text": {
        "azure_service": "Speech Service",
        "azure_category": "AI + Machine Learning",
        "azure_resource_type": "Microsoft.CognitiveServices/accounts",
        "description": "Speech recognition",
        "cost": {"gcp_monthly": 24, "azure_monthly": 18, "currency": "USD", "assumptions": "10 hours audio"},
    },
    
    # Security & Identity
    "cloud iam": {
        "azure_service": "Azure Active Directory",
        "azure_category": "Identity",
        "azure_resource_type": "Microsoft.ManagedIdentity/userAssignedIdentities",
        "description": "Identity and access management",
        "cost": {"gcp_monthly": 0, "azure_monthly": 0, "currency": "USD", "assumptions": "Free tier"},
    },
    "identity and access management": {
        "azure_service": "Azure Active Directory",
        "azure_category": "Identity",
        "azure_resource_type": "Microsoft.ManagedIdentity/userAssignedIdentities",
        "description": "Identity and access management",
        "cost": {"gcp_monthly": 0, "azure_monthly": 0, "currency": "USD", "assumptions": "Free tier"},
    },
    "cloud armor": {
        "azure_service": "Azure DDoS Protection",
        "azure_category": "Security",
        "azure_resource_type": "Microsoft.Network/ddosProtectionPlans",
        "description": "DDoS protection and WAF",
        "cost": {"gcp_monthly": 0, "azure_monthly": 2944, "currency": "USD", "assumptions": "Standard tier - GCP included"},
    },
    "cloud kms": {
        "azure_service": "Azure Key Vault",
        "azure_category": "Security",
        "azure_resource_type": "Microsoft.KeyVault/vaults",
        "description": "Key management service",
        "cost": {"gcp_monthly": 3, "azure_monthly": 3, "currency": "USD", "assumptions": "10K operations"},
    },
    "secret manager": {
        "azure_service": "Azure Key Vault",
        "azure_category": "Security",
        "azure_resource_type": "Microsoft.KeyVault/vaults",
        "description": "Secrets management",
        "cost": {"gcp_monthly": 1, "azure_monthly": 2, "currency": "USD", "assumptions": "1K operations"},
    },
    
    # Monitoring & Operations
    "cloud monitoring": {
        "azure_service": "Azure Monitor",
        "azure_category": "Management + Governance",
        "azure_resource_type": "Microsoft.Insights/components",
        "description": "Infrastructure monitoring",
        "cost": {"gcp_monthly": 8, "azure_monthly": 10, "currency": "USD", "assumptions": "Basic metrics"},
    },
    "stackdriver": {
        "azure_service": "Azure Monitor",
        "azure_category": "Management + Governance",
        "azure_resource_type": "Microsoft.Insights/components",
        "description": "Infrastructure monitoring",
        "cost": {"gcp_monthly": 8, "azure_monthly": 10, "currency": "USD", "assumptions": "Basic metrics"},
    },
    "cloud logging": {
        "azure_service": "Azure Monitor Logs",
        "azure_category": "Management + Governance",
        "azure_resource_type": "Microsoft.OperationalInsights/workspaces",
        "description": "Centralized logging",
        "cost": {"gcp_monthly": 50, "azure_monthly": 60, "currency": "USD", "assumptions": "50GB ingestion"},
    },
    "cloud trace": {
        "azure_service": "Application Insights",
        "azure_category": "Management + Governance",
        "azure_resource_type": "Microsoft.Insights/components",
        "description": "Distributed tracing",
        "cost": {"gcp_monthly": 0, "azure_monthly": 0, "currency": "USD", "assumptions": "Included with App Insights"},
    },
    
    # Data Analytics
    "dataflow": {
        "azure_service": "Azure Stream Analytics",
        "azure_category": "Analytics",
        "azure_resource_type": "Microsoft.StreamAnalytics/streamingjobs",
        "description": "Stream and batch processing",
        "cost": {"gcp_monthly": 100, "azure_monthly": 90, "currency": "USD", "assumptions": "Basic processing"},
    },
    "dataproc": {
        "azure_service": "Azure HDInsight",
        "azure_category": "Analytics",
        "azure_resource_type": "Microsoft.HDInsight/clusters",
        "description": "Managed Spark and Hadoop",
        "cost": {"gcp_monthly": 200, "azure_monthly": 220, "currency": "USD", "assumptions": "3-node cluster"},
    },
    "data fusion": {
        "azure_service": "Azure Data Factory",
        "azure_category": "Analytics",
        "azure_resource_type": "Microsoft.DataFactory/factories",
        "description": "Data integration service",
        "cost": {"gcp_monthly": 150, "azure_monthly": 140, "currency": "USD", "assumptions": "Basic pipelines"},
    },
    
    # IoT & Edge
    "iot core": {
        "azure_service": "Azure IoT Hub",
        "azure_category": "IoT",
        "azure_resource_type": "Microsoft.Devices/IotHubs",
        "description": "IoT device management",
        "cost": {"gcp_monthly": 0, "azure_monthly": 25, "currency": "USD", "assumptions": "Basic tier"},
    },
    
    # Developer Tools
    "cloud build": {
        "azure_service": "Azure DevOps Pipelines",
        "azure_category": "DevOps",
        "azure_resource_type": "Microsoft.DevOps/pipelines",
        "description": "CI/CD pipeline service",
        "cost": {"gcp_monthly": 0, "azure_monthly": 0, "currency": "USD", "assumptions": "Free tier 1800 minutes"},
    },
    "artifact registry": {
        "azure_service": "Azure Artifacts",
        "azure_category": "DevOps",
        "azure_resource_type": "Microsoft.DevOps/artifacts",
        "description": "Package repository",
        "cost": {"gcp_monthly": 5, "azure_monthly": 2, "currency": "USD", "assumptions": "2GB storage"},
    },
    "cloud source repositories": {
        "azure_service": "Azure Repos",
        "azure_category": "DevOps",
        "azure_resource_type": "Microsoft.DevOps/repos",
        "description": "Git repositories",
        "cost": {"gcp_monthly": 0, "azure_monthly": 0, "currency": "USD", "assumptions": "Free tier"},
    },
}


# Service type to GCP service name mapping for imported inventory
SERVICE_TYPE_TO_GCP: Dict[str, str] = {
    "virtual_machine": "compute engine",
    "instance_template": "compute engine",
    "instance_group": "compute engine",
    "disk": "persistent disk",
    "vpc": "virtual private cloud",
    "subnet": "virtual private cloud",
    "firewall": "cloud armor",
    "external_ip": "virtual private cloud",
    "load_balancer": "cloud load balancing",
    "backend_service": "cloud load balancing",
    "url_map": "cloud load balancing",
    "kubernetes": "google kubernetes engine",
    "cloud_run": "cloud run",
    "cloud_function": "cloud functions",
    "cloud_storage": "cloud storage",
    "cloud_sql": "cloud sql",
    "spanner": "cloud spanner",
    "bigtable": "cloud bigtable",
    "firestore": "cloud firestore",
    "memorystore": "memorystore",
    "pubsub_topic": "cloud pub/sub",
    "pubsub_subscription": "cloud pub/sub",
    "cloud_tasks": "cloud tasks",
    "secret_manager": "secret manager",
    "cloud_kms": "cloud key management",
    "service_account": "cloud iam",
    "monitoring_alert": "cloud monitoring",
    "logging_sink": "cloud logging",
    "vertex_ai": "vertex ai",
}


def _resolve_mapping(service_name: str) -> Optional[Dict[str, Any]]:
    """Attempt to find a GCP→Azure mapping for the normalized service name."""
    normalized = _normalize(service_name)
    if not normalized:
        return None

    # Direct match
    if normalized in GCP_TO_AZURE_MAPPINGS:
        return GCP_TO_AZURE_MAPPINGS[normalized]

    # Partial match
    for key, mapping in GCP_TO_AZURE_MAPPINGS.items():
        if key in normalized or normalized in key:
            return mapping

    return None


def migrate_gcp_diagram(diagram: Dict[str, Any] | None) -> GcpMigrationResult:
    """Convert GCP-tagged nodes inside a diagram into Azure equivalents."""
    if not isinstance(diagram, dict):
        return GcpMigrationResult(diagram={}, applied=False)

    nodes = deepcopy(diagram.get("nodes") or [])
    converted_nodes: List[Dict[str, Any]] = []
    price_summary: List[Dict[str, Any]] = []
    bicep_snippets: List[Dict[str, Any]] = []
    unmapped_services: List[Dict[str, Any]] = []

    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data") or {}
        if not isinstance(data, dict):
            continue
        provider_hint = _normalize(str(data.get("provider", "")))
        title = data.get("title") or data.get("label") or node.get("id") or ""
        normalized_title = _normalize(str(title))
        
        # Get serviceType for better matching on imported inventory
        service_type = data.get("serviceType") or ""

        if provider_hint not in ("gcp",) and not normalized_title:
            continue

        original_snapshot = {
            "title": data.get("title"),
            "category": data.get("category"),
            "iconPath": data.get("iconPath"),
            "provider": data.get("provider", "gcp"),
            "serviceType": service_type,
        }

        # Try to resolve mapping - first try serviceType, then title
        mapping = None
        
        # Try serviceType-based mapping first (more reliable for imported inventory)
        if service_type and service_type in SERVICE_TYPE_TO_GCP:
            gcp_service_name = SERVICE_TYPE_TO_GCP[service_type]
            mapping = _resolve_mapping(gcp_service_name)
        
        # Fall back to title-based mapping
        if not mapping:
            mapping = _resolve_mapping(normalized_title)
            
        if not mapping:
            data.setdefault("badges", [])
            if "Unmapped" not in data["badges"]:
                data["badges"].append("Unmapped")
            data.setdefault("notes", "GCP service not yet mapped to an Azure equivalent")
            unmapped_services.append(
                {
                    "node_id": node.get("id"),
                    "gcp_service": original_snapshot["title"],
                    "reason": "No Azure mapping available",
                }
            )
            continue

        data["gcpOriginal"] = original_snapshot
        data["provider"] = "azure"
        data["title"] = mapping["azure_service"]
        data["category"] = mapping["azure_category"]
        data["resourceType"] = mapping["azure_resource_type"]
        data.setdefault("badges", [])
        data["badges"] = list(set([*data["badges"], "Migrated"]))
        node["data"] = data

        converted_nodes.append(
            {
                "node_id": node.get("id"),
                "gcp_service": original_snapshot["title"],
                "azure_service": mapping["azure_service"],
                "resource_type": mapping["azure_resource_type"],
                "description": mapping.get("description"),
            }
        )

        if mapping.get("cost"):
            cost = mapping["cost"]
            summary_entry = {
                "node_id": node.get("id"),
                "gcp_service": original_snapshot["title"],
                "azure_service": mapping["azure_service"],
                "currency": cost.get("currency", "USD"),
                "gcp_monthly": cost.get("gcp_monthly"),
                "azure_monthly": cost.get("azure_monthly"),
                "delta": None,
                "assumptions": cost.get("assumptions"),
            }
            gcp_price = cost.get("gcp_monthly")
            azure_price = cost.get("azure_monthly")
            if isinstance(gcp_price, (int, float)) and isinstance(azure_price, (int, float)):
                summary_entry["delta"] = azure_price - gcp_price
            price_summary.append(summary_entry)

        if mapping.get("bicep_template"):
            bicep_snippets.append(
                {
                    "gcp_service": original_snapshot["title"],
                    "azure_service": mapping["azure_service"],
                    "snippet": mapping["bicep_template"],
                }
            )

    updated_diagram = dict(diagram)
    updated_diagram["nodes"] = nodes

    applied = bool(converted_nodes)
    if applied:
        logger.info("Migrated %s GCP nodes to Azure equivalents", len(converted_nodes))
    if unmapped_services:
        logger.info("Found %s unmapped GCP services", len(unmapped_services))

    cost_summary = _build_cost_summary(price_summary)
    return GcpMigrationResult(
        diagram=updated_diagram,
        converted_nodes=converted_nodes,
        price_summary=price_summary,
        cost_summary=cost_summary,
        bicep_snippets=bicep_snippets,
        unmapped_services=unmapped_services,
        applied=applied,
    )
