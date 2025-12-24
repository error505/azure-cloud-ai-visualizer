"""
Utilities for migrating AWS-native diagrams into Azure-native representations.

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
class AwsMigrationResult:
    """Structured result of a migration pass."""

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
    return """@description('Virtual machine that replaces the EC2 instance')
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
    return """@description('Azure Function replacing AWS Lambda')
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
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};'
        }
      ]
    }
  }
}
"""


def _bicep_storage_snippet() -> str:
    return """@description('Storage account replacing Amazon S3')
param location string = resourceGroup().location
param storageAccountName string = 'st${uniqueString(resourceGroup().id)}'

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_GRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
  }
}
"""


def _bicep_cosmos_snippet() -> str:
    return """@description('Azure Cosmos DB replacing Amazon DynamoDB')
param location string = resourceGroup().location
param accountName string = 'cosmos${uniqueString(resourceGroup().id)}'

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: accountName
  location: location
  locations: [
    {
      locationName: location
      failoverPriority: 0
      isZoneRedundant: true
    }
  ]
  properties: {
    databaseAccountOfferType: 'Standard'
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}
"""


def _bicep_sql_snippet() -> str:
    return """@description('Azure SQL Database replacing Amazon RDS')
param location string = resourceGroup().location
param sqlServerName string = 'sql${uniqueString(resourceGroup().id)}'
param sqlDbName string = 'sqldb${uniqueString(resourceGroup().id)}'

resource sqlServer 'Microsoft.Sql/servers@2022-05-01-preview' = {
  name: sqlServerName
  location: location
  properties: {
    administratorLogin: 'sqladminuser'
    administratorLoginPassword: 'P@ssw0rd1234!'
  }
}

resource sqlDb 'Microsoft.Sql/servers/databases@2022-05-01-preview' = {
  name: '${sqlServer.name}/${sqlDbName}'
  location: location
  properties: {
    sku: {
      name: 'GP_Gen5_2'
      tier: 'GeneralPurpose'
    }
  }
}
"""


def _bicep_api_management_snippet() -> str:
    return """@description('Azure API Management replacing Amazon API Gateway')
param location string = resourceGroup().location
param apiManagementName string = 'apim-${uniqueString(resourceGroup().id)}'

resource apim 'Microsoft.ApiManagement/service@2023-03-01-preview' = {
  name: apiManagementName
  location: location
  sku: {
    name: 'Developer'
    capacity: 1
  }
  properties: {
    publisherEmail: 'admin@example.com'
    publisherName: 'Cloud Visualizer'
  }
}
"""


def _bicep_vnet_snippet() -> str:
    return """@description('Azure Virtual Network replacing Amazon VPC')
param location string = resourceGroup().location
param vnetName string = 'vnet-${uniqueString(resourceGroup().id)}'

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2023-04-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [
        '10.10.0.0/16'
      ]
    }
    subnets: [
      {
        name: 'workloads'
        properties: {
          addressPrefix: '10.10.1.0/24'
        }
      }
    ]
  }
}
"""


def _bicep_service_bus_snippet() -> str:
    return """@description('Azure Service Bus replacing Amazon SQS/SNS')
param location string = resourceGroup().location
param namespaceName string = 'sb${uniqueString(resourceGroup().id)}'

resource serviceBus 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: namespaceName
  location: location
  sku: {
    name: 'Premium'
    tier: 'Premium'
    capacity: 1
  }
}
"""


def _bicep_front_door_snippet() -> str:
    return """@description('Azure Front Door replacing Amazon CloudFront')
param fwName string = 'afd-${uniqueString(resourceGroup().id)}'

resource frontDoor 'Microsoft.Cdn/profiles@2023-05-01' = {
  name: fwName
  location: 'global'
  sku: {
    name: 'Premium_AzureFrontDoor'
  }
}
"""


def _bicep_static_web_app_snippet() -> str:
    return """@description('Azure Static Web App replacing AWS Amplify')
param location string = resourceGroup().location
param appName string = 'swa-${uniqueString(resourceGroup().id)}'

resource staticApp 'Microsoft.Web/staticSites@2022-09-01' = {
  name: appName
  location: location
  properties: {
    repositoryUrl: 'https://github.com/contoso/frontend'
    branch: 'main'
    buildProperties: {
      appLocation: '/'
      apiLocation: 'api'
      outputLocation: 'build'
    }
  }
}
"""


def _bicep_logic_app_snippet() -> str:
    return """@description('Azure Logic App replacing AWS Step Functions')
param location string = resourceGroup().location
param logicAppName string = 'logic-${uniqueString(resourceGroup().id)}'

resource logicApp 'Microsoft.Logic/workflows@2019-05-01' = {
  name: logicAppName
  location: location
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      actions: {}
      outputs: {}
      parameters: {}
      triggers: {}
    }
  }
}
"""


def _bicep_form_recognizer_snippet() -> str:
    return """@description('Azure AI Form Recognizer replacing Amazon Textract')
param location string = resourceGroup().location
param accountName string = 'form${uniqueString(resourceGroup().id)}'

resource formRecognizer 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: accountName
  location: location
  kind: 'FormRecognizer'
  sku: {
    name: 'S0'
  }
  properties: {}
}
"""


def _bicep_vision_snippet() -> str:
    return """@description('Azure AI Vision replacing Amazon Rekognition')
param location string = resourceGroup().location
param accountName string = 'vision${uniqueString(resourceGroup().id)}'

resource vision 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: accountName
  location: location
  kind: 'CognitiveServices'
  sku: {
    name: 'S0'
  }
  properties: {}
}
"""


def _bicep_translator_snippet() -> str:
    return """@description('Azure AI Translator replacing Amazon Translate')
param location string = resourceGroup().location
param accountName string = 'translator${uniqueString(resourceGroup().id)}'

resource translator 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: accountName
  location: location
  kind: 'TextTranslation'
  sku: {
    name: 'S1'
  }
  properties: {}
}
"""


def _bicep_speech_snippet() -> str:
    return """@description('Azure AI Speech replacing Amazon Polly')
param location string = resourceGroup().location
param accountName string = 'speech${uniqueString(resourceGroup().id)}'

resource speech 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: accountName
  location: location
  kind: 'SpeechServices'
  sku: {
    name: 'S0'
  }
  properties: {}
}
"""


def _bicep_machinlearning_workspace_snippet() -> str:
    return """@description('Azure Machine Learning replacing Amazon SageMaker')
param location string = resourceGroup().location
param workspaceName string = 'aml-${uniqueString(resourceGroup().id)}'

resource amlWorkspace 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: workspaceName
  location: location
  properties: {
    friendlyName: workspaceName
    description: 'Workspace migrated from SageMaker'
  }
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
}
"""


def _bicep_aad_b2c_snippet() -> str:
    return """@description('Azure AD B2C replacing Amazon Cognito')
param tenantName string = 'b2c${uniqueString(resourceGroup().id)}'

resource b2cDirectory 'Microsoft.AzureActiveDirectory/b2cDirectories@2019-01-01-preview' = {
  name: tenantName
  location: 'Europe'
  properties: {
    createTenantProperties: {
      countryCode: 'US'
      displayName: tenantName
      domainName: '${tenantName}.onmicrosoft.com'
    }
  }
}
"""




AWS_TO_AZURE_SERVICE_CATALOG: Sequence[Dict[str, Any]] = [
    {
        "aws": ["amazon ec2", "aws ec2", "ec2", "elastic compute cloud"],
        "azure_service": "Azure Virtual Machine",
        "azure_category": "Compute",
        "azure_resource_type": "Microsoft.Compute/virtualMachines",
        "description": "General purpose compute nodes transferred from EC2 to Azure Virtual Machines.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 52.0,
            "azure_monthly": 48.5,
            "assumptions": "2 vCPU, 8 GiB, 730 hours/month",
        },
        "bicep_template": _bicep_vm_snippet(),
    },
    {
        "aws": ["aws lambda", "lambda", "amazon lambda", "serverless function"],
        "azure_service": "Azure Functions",
        "azure_category": "Compute",
        "azure_resource_type": "Microsoft.Web/sites/functions",
        "description": "Event-driven compute mapped to Azure Functions (Consumption plan).",
        "cost": {
            "currency": "USD",
            "aws_monthly": 20.0,
            "azure_monthly": 18.0,
            "assumptions": "50M executions, 1M GB-seconds",
        },
        "bicep_template": _bicep_functions_snippet(),
    },
    {
        "aws": ["amazon s3", "s3", "simple storage service", "aws s3 bucket"],
        "azure_service": "Azure Storage Account",
        "azure_category": "Storage",
        "azure_resource_type": "Microsoft.Storage/storageAccounts",
        "description": "Object storage moved from S3 to geo-redundant StorageV2.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 23.5,
            "azure_monthly": 22.0,
            "assumptions": "5 TB hot data, 10M read/write operations",
        },
        "bicep_template": _bicep_storage_snippet(),
    },
    {
        "aws": ["amazon rds", "rds", "relational database service"],
        "azure_service": "Azure SQL Database",
        "azure_category": "Data",
        "azure_resource_type": "Microsoft.Sql/servers/databases",
        "description": "Managed relational database migrated to Azure SQL single database.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 150.0,
            "azure_monthly": 140.0,
            "assumptions": "General-purpose, 2 vCore, 512 GB storage",
        },
        "bicep_template": _bicep_sql_snippet(),
    },
    {
        "aws": ["amazon dynamodb", "dynamodb"],
        "azure_service": "Azure Cosmos DB",
        "azure_category": "Data",
        "azure_resource_type": "Microsoft.DocumentDB/databaseAccounts",
        "description": "Serverless document database backed by Cosmos DB with session consistency.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 60.0,
            "azure_monthly": 55.0,
            "assumptions": "1000 RUs/s, multi-region write disabled",
        },
        "bicep_template": _bicep_cosmos_snippet(),
    },
    {
        "aws": ["amazon api gateway", "api gateway", "aws api gateway"],
        "azure_service": "Azure API Management",
        "azure_category": "Integration",
        "azure_resource_type": "Microsoft.ApiManagement/service",
        "description": "Centralized API gateway with policy enforcement via APIM.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 35.0,
            "azure_monthly": 40.0,
            "assumptions": "3M calls/month, developer tier",
        },
        "bicep_template": _bicep_api_management_snippet(),
    },
    {
        "aws": ["amazon vpc", "vpc", "virtual private cloud"],
        "azure_service": "Azure Virtual Network",
        "azure_category": "Networking",
        "azure_resource_type": "Microsoft.Network/virtualNetworks",
        "description": "Network segmentation moved from VPC to peered VNets.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 0.0,
            "azure_monthly": 0.0,
            "assumptions": "Baseline VNet/subnet construct",
        },
        "bicep_template": _bicep_vnet_snippet(),
    },
    {
        "aws": ["amazon ecs", "amazon eks", "ecs", "eks", "fargate"],
        "azure_service": "Azure Kubernetes Service",
        "azure_category": "Containers",
        "azure_resource_type": "Microsoft.ContainerService/managedClusters",
        "description": "Containers orchestrated with AKS replacing ECS/EKS control plane.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 74.0,
            "azure_monthly": 70.0,
            "assumptions": "Two-node pool, burstable instances",
        },
        "bicep_template": """@description('Azure Kubernetes Service replacing Amazon ECS/EKS')
param location string = resourceGroup().location
param clusterName string = 'aks-${uniqueString(resourceGroup().id)}'

resource aks 'Microsoft.ContainerService/managedClusters@2024-01-01' = {
  name: clusterName
  location: location
  sku: {
    name: 'Base'
    tier: 'Standard'
  }
  properties: {
    dnsPrefix: clusterName
    kubernetesVersion: '1.29.0'
    agentPoolProfiles: [
      {
        name: 'systempool'
        count: 2
        vmSize: 'Standard_B4ms'
        osType: 'Linux'
        type: 'VirtualMachineScaleSets'
        mode: 'System'
      }
    ]
  }
}
""",
    },
    {
        "aws": ["amazon sqs", "sqs", "amazon sns", "sns", "simple queue service", "simple notification service"],
        "azure_service": "Azure Service Bus",
        "azure_category": "Integration",
        "azure_resource_type": "Microsoft.ServiceBus/namespaces",
        "description": "Messaging workloads consolidated on Service Bus Premium namespaces.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 5.0,
            "azure_monthly": 4.5,
            "assumptions": "10M operations, 1 Premium namespace",
        },
        "bicep_template": _bicep_service_bus_snippet(),
    },
    {
        "aws": ["amazon cloudfront", "cloudfront", "cdn"],
        "azure_service": "Azure Front Door",
        "azure_category": "Networking",
        "azure_resource_type": "Microsoft.Cdn/profiles",
        "description": "Global CDN/front-door distribution based on Azure Front Door Premium.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 35.0,
            "azure_monthly": 32.0,
            "assumptions": "10 TB egress, standard rules engine",
        },
        "bicep_template": _bicep_front_door_snippet(),
    },
    {
        "aws": ["aws amplify", "amplify", "amazon amplify"],
        "azure_service": "Azure Static Web Apps",
        "azure_category": "Web",
        "azure_resource_type": "Microsoft.Web/staticSites",
        "description": "Static front-end hosting migrated from Amplify to Azure Static Web Apps.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 19.0,
            "azure_monthly": 17.0,
            "assumptions": "Standard tier, 1 custom domain",
        },
        "bicep_template": _bicep_static_web_app_snippet(),
    },
    {
        "aws": ["amazon cognito", "cognito"],
        "azure_service": "Azure AD B2C",
        "azure_category": "Identity",
        "azure_resource_type": "Microsoft.AzureActiveDirectory/b2cDirectories",
        "description": "Customer identity platform migrated from Amazon Cognito to Azure AD B2C.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 30.0,
            "azure_monthly": 28.0,
            "assumptions": "50k MAU, standard tier",
        },
        "bicep_template": _bicep_aad_b2c_snippet(),
    },
    {
        "aws": ["aws step functions", "step functions"],
        "azure_service": "Azure Logic Apps",
        "azure_category": "Integration",
        "azure_resource_type": "Microsoft.Logic/workflows",
        "description": "State orchestration moved from Step Functions to Logic Apps.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 45.0,
            "azure_monthly": 42.0,
            "assumptions": "5M actions per month",
        },
        "bicep_template": _bicep_logic_app_snippet(),
    },
    {
        "aws": ["amazon textract", "textract"],
        "azure_service": "Azure AI Form Recognizer",
        "azure_category": "AI",
        "azure_resource_type": "Microsoft.CognitiveServices/accounts",
        "description": "Document extraction capabilities migrated from Textract to Form Recognizer.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 60.0,
            "azure_monthly": 58.0,
            "assumptions": "1M pages analyzed",
        },
        "bicep_template": _bicep_form_recognizer_snippet(),
    },
    {
        "aws": ["amazon rekognition", "rekognition"],
        "azure_service": "Azure AI Vision",
        "azure_category": "AI",
        "azure_resource_type": "Microsoft.CognitiveServices/accounts",
        "description": "Computer vision pipelines migrated from Rekognition to Azure AI Vision.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 40.0,
            "azure_monthly": 39.0,
            "assumptions": "2M images per month",
        },
        "bicep_template": _bicep_vision_snippet(),
    },
    {
        "aws": ["amazon sagemaker", "sagemaker"],
        "azure_service": "Azure Machine Learning",
        "azure_category": "AI",
        "azure_resource_type": "Microsoft.MachineLearningServices/workspaces",
        "description": "Managed ML workspace migrated from SageMaker to Azure Machine Learning.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 120.0,
            "azure_monthly": 115.0,
            "assumptions": "Basic dev workspace",
        },
        "bicep_template": _bicep_machinlearning_workspace_snippet(),
    },
    {
        "aws": ["amazon translate", "translate"],
        "azure_service": "Azure AI Translator",
        "azure_category": "AI",
        "azure_resource_type": "Microsoft.CognitiveServices/accounts",
        "description": "Text translation migrated from Amazon Translate to Azure AI Translator.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 25.0,
            "azure_monthly": 24.0,
            "assumptions": "20M characters per month",
        },
        "bicep_template": _bicep_translator_snippet(),
    },
    {
        "aws": ["amazon polly", "polly"],
        "azure_service": "Azure AI Speech",
        "azure_category": "AI",
        "azure_resource_type": "Microsoft.CognitiveServices/accounts",
        "description": "Text-to-speech output migrated from Amazon Polly to Azure AI Speech.",
        "cost": {
            "currency": "USD",
            "aws_monthly": 35.0,
            "azure_monthly": 34.0,
            "assumptions": "5M characters per month",
        },
        "bicep_template": _bicep_speech_snippet(),
    },
]

AWS_LOOKUP: Dict[str, Dict[str, Any]] = {}
for entry in AWS_TO_AZURE_SERVICE_CATALOG:
    for alias in entry.get("aws", []):
        AWS_LOOKUP[_normalize(alias)] = entry


def _as_number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_cost_summary(price_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not price_rows:
        return {}

    numeric_rows: List[Dict[str, Any]] = []
    currency = "USD"
    for row in price_rows:
        aws_price = _as_number(row.get("aws_monthly"))
        azure_price = _as_number(row.get("azure_monthly"))
        if isinstance(row.get("currency"), str):
            currency = row["currency"]
        if aws_price is None and azure_price is None:
            continue

        delta = None
        if aws_price is not None and azure_price is not None:
            delta = azure_price - aws_price

        entry = dict(row)
        entry["aws_monthly"] = aws_price
        entry["azure_monthly"] = azure_price
        entry["delta"] = delta
        # Use explicit None checks so static analyzers know aws_price and delta are present,
        # and compute savings using delta to avoid subtracting a float and None.
        if (aws_price is not None) and (delta is not None):
            try:
                if aws_price == 0:
                    entry["savings_percent"] = None
                else:
                    # delta = azure_price - aws_price, so savings_percent = (aws - azure) / aws * 100 = (-delta)/aws * 100
                    entry["savings_percent"] = round(((-delta) / aws_price) * 100, 2)
            except Exception:
                entry["savings_percent"] = None
        else:
            entry["savings_percent"] = None

        numeric_rows.append(entry)

    if not numeric_rows:
        return {}

    aws_total = sum(filter(None, (row.get("aws_monthly") for row in numeric_rows)))
    azure_total = sum(filter(None, (row.get("azure_monthly") for row in numeric_rows)))
    delta_total = azure_total - aws_total
    savings = aws_total - azure_total
    savings_percent = None
    if aws_total:
        savings_percent = round((savings / aws_total) * 100, 2)

    verdict: str
    if savings > 0:
        verdict = f"Migrating to Azure saves approximately {currency} {abs(savings):,.2f} per month."
    elif savings < 0:
        verdict = f"Migrating to Azure adds approximately {currency} {abs(savings):,.2f} per month."
    else:
        verdict = "Monthly costs are roughly equivalent between AWS and Azure for this workload."

    summary_lines = [
        f"- **AWS monthly**: {currency} {aws_total:,.2f}",
        f"- **Azure monthly**: {currency} {azure_total:,.2f}",
        f"- **Delta**: {currency} {delta_total:,.2f}",
    ]
    if savings_percent is not None:
        summary_lines.append(f"- **Projected savings**: {savings_percent:+.2f}% vs AWS")

    return {
        "currency": currency,
        "aws_monthly_total": aws_total,
        "azure_monthly_total": azure_total,
        "delta": delta_total,
        "savings": savings,
        "savings_percent": savings_percent,
        "verdict": verdict,
        "summary_markdown": "\n".join(summary_lines),
        "per_service": numeric_rows,
    }


# Service type to AWS service name mapping for imported inventory
SERVICE_TYPE_TO_AWS: Dict[str, str] = {
    "virtual_machine": "amazon ec2",
    "function": "aws lambda",
    "ecs_cluster": "amazon ecs",
    "ecs_service": "amazon ecs",
    "ecs_task": "amazon ecs",
    "kubernetes": "amazon eks",
    "container_registry": "amazon ecr",
    "rds": "amazon rds",
    "rds_cluster": "amazon aurora",
    "dynamodb": "amazon dynamodb",
    "elasticache": "amazon elasticache",
    "object_storage": "amazon s3",
    "vpc": "amazon vpc",
    "subnet": "amazon vpc",
    "load_balancer": "elastic load balancing",
    "target_group": "elastic load balancing",
    "security_group": "amazon vpc",
    "internet_gateway": "amazon vpc",
    "nat_gateway": "amazon vpc",
    "cloudfront": "amazon cloudfront",
    "route53": "amazon route 53",
    "api_gateway": "amazon api gateway",
    "api_gateway_v2": "amazon api gateway",
    "queue": "amazon sqs",
    "topic": "amazon sns",
    "step_functions": "aws step functions",
    "kms": "aws kms",
    "secrets_manager": "aws secrets manager",
    "iam_role": "aws iam",
    "iam_user": "aws iam",
    "cognito": "amazon cognito",
    "cloudwatch_alarm": "amazon cloudwatch",
    "cloudwatch_logs": "amazon cloudwatch",
    "sagemaker": "amazon sagemaker",
}


def _resolve_mapping(service_name: str) -> Optional[Dict[str, Any]]:
    normalized = _normalize(service_name)
    if not normalized:
        return None
    mapping = AWS_LOOKUP.get(normalized)
    if mapping:
        return mapping
    # Fuzzy fallback: find the first alias contained within the name.
    for alias, entry in AWS_LOOKUP.items():
        if alias and (alias in normalized or normalized in alias):
            return entry
    return None


def migrate_aws_diagram(diagram: Dict[str, Any] | None) -> AwsMigrationResult:
    """Convert AWS-tagged nodes inside a diagram into Azure equivalents."""
    if not isinstance(diagram, dict):
        return AwsMigrationResult(diagram={}, applied=False)

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

        if provider_hint not in ("aws",) and not normalized_title:
            continue

        original_snapshot = {
            "title": data.get("title"),
            "category": data.get("category"),
            "iconPath": data.get("iconPath"),
            "provider": data.get("provider", "aws"),
            "serviceType": service_type,
        }

        # Try to resolve mapping - first try serviceType, then title
        mapping = None
        
        # Try serviceType-based mapping first (more reliable for imported inventory)
        if service_type and service_type in SERVICE_TYPE_TO_AWS:
            aws_service_name = SERVICE_TYPE_TO_AWS[service_type]
            mapping = _resolve_mapping(aws_service_name)
        
        # Fall back to title-based mapping
        if not mapping:
            mapping = _resolve_mapping(normalized_title)
        
        if not mapping:
            data.setdefault("badges", [])
            if "Unmapped" not in data["badges"]:
                data["badges"].append("Unmapped")
            data.setdefault("notes", "AWS service not yet mapped to an Azure equivalent")
            unmapped_services.append(
                {
                    "node_id": node.get("id"),
                    "aws_service": original_snapshot["title"],
                    "reason": "No Azure mapping available",
                }
            )
            continue

        data["awsOriginal"] = original_snapshot
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
                "aws_service": original_snapshot["title"],
                "azure_service": mapping["azure_service"],
                "resource_type": mapping["azure_resource_type"],
                "description": mapping.get("description"),
            }
        )

        if mapping.get("cost"):
            cost = mapping["cost"]
            summary_entry = {
                "node_id": node.get("id"),
                "aws_service": original_snapshot["title"],
                "azure_service": mapping["azure_service"],
                "currency": cost.get("currency", "USD"),
                "aws_monthly": cost.get("aws_monthly"),
                "azure_monthly": cost.get("azure_monthly"),
                "delta": None,
                "assumptions": cost.get("assumptions"),
            }
            aws_price = cost.get("aws_monthly")
            azure_price = cost.get("azure_monthly")
            if isinstance(aws_price, (int, float)) and isinstance(azure_price, (int, float)):
                summary_entry["delta"] = azure_price - aws_price
            price_summary.append(summary_entry)

        if mapping.get("bicep_template"):
            bicep_snippets.append(
                {
                    "aws_service": original_snapshot["title"],
                    "azure_service": mapping["azure_service"],
                    "snippet": mapping["bicep_template"],
                }
            )

    updated_diagram = dict(diagram)
    updated_diagram["nodes"] = nodes
    applied = bool(converted_nodes)
    if applied:
        logger.info("Migrated %s AWS nodes to Azure equivalents", len(converted_nodes))
    if unmapped_services:
        logger.info("Found %s unmapped AWS services", len(unmapped_services))
    cost_summary = _build_cost_summary(price_summary)
    return AwsMigrationResult(
        diagram=updated_diagram,
        converted_nodes=converted_nodes,
        price_summary=price_summary,
        cost_summary=cost_summary,
        bicep_snippets=bicep_snippets,
        unmapped_services=unmapped_services,
        applied=applied,
    )
