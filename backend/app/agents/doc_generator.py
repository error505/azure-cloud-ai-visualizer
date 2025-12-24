"""
AI Documentation Generator

Automatically generates enterprise-grade documentation from architecture diagrams:
- **HLD (High-Level Design)**: Architecture overview, components, data flows
- **LLD (Low-Level Design)**: Detailed service specs, configurations, APIs
- **Runbook**: Operational procedures, troubleshooting, maintenance
- **Deployment Guide**: Step-by-step deployment instructions

Saves weeks of manual documentation work!
"""

import json
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class DocumentationMetadata:
    """Metadata for generated documentation."""
    document_type: str  # hld, lld, runbook, deployment_guide
    generated_at: str
    diagram_services_count: int
    version: str = "1.0"


class DocumentationGenerator:
    """Generates comprehensive technical documentation from architecture diagrams."""
    
    def __init__(self, agent_client):
        """
        Initialize with agent client.
        
        Args:
            agent_client: Client supporting create_agent()
        """
        self.agent_client = agent_client
        self.doc_agent = None
        
    async def initialize(self):
        """Create the documentation generation agent."""
        logger.info("Initializing Documentation Generator...")
        
        doc_instructions = """You are a technical documentation specialist creating enterprise-grade architecture documentation.

Your documentation must be:
- **Comprehensive**: Cover all services, integrations, and data flows
- **Clear**: Use diagrams, tables, and structured sections
- **Actionable**: Include specific configurations, commands, and procedures
- **Professional**: Follow technical writing best practices

Always structure documentation with proper headings, numbered sections, and markdown formatting.
"""
        
        try:
            self.doc_agent = self.agent_client.create_agent(
                name="DocumentationAgent",
                instructions=doc_instructions
            )
            logger.info("Documentation generator initialized")
        except Exception as e:
            logger.error(f"Failed to initialize documentation agent: {e}")
            raise
    
    async def generate_hld(
        self,
        diagram: Dict[str, Any],
        requirements: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate High-Level Design (HLD) document.
        
        Includes:
        - Executive summary
        - System architecture overview
        - Component descriptions
        - Data flow diagrams
        - Integration points
        - Technology stack
        - Security overview
        - Scalability approach
        
        Args:
            diagram: ReactFlow diagram
            requirements: Optional original requirements
            
        Returns:
            HLD document in markdown format with metadata
        """
        if not self.doc_agent:
            await self.initialize()
        
        nodes = diagram.get('nodes', [])
        edges = diagram.get('edges', [])
        
        prompt = f"""Generate a comprehensive High-Level Design (HLD) document for this Azure architecture.

ARCHITECTURE DIAGRAM:
- Services: {len(nodes)} total
- Integrations: {len(edges)} connections
- Diagram: {json.dumps(diagram, indent=2)[:5000]}...

{f"ORIGINAL REQUIREMENTS:\\n{requirements}\\n" if requirements else ""}

Create a professional HLD with these sections:

# High-Level Design Document

## 1. Executive Summary
[Brief overview of the system, its purpose, and key capabilities]

## 2. System Architecture Overview
[High-level description of the architecture approach and principles]

## 3. Components
[For each major service/component, describe its purpose, responsibilities, and key features]

## 4. Data Flows
[Describe how data moves through the system, including ingestion, processing, storage, and retrieval]

## 5. Integration Points
[List all external systems, APIs, and third-party services with integration patterns]

## 6. Technology Stack
[Complete list of Azure services used with rationale for each choice]

## 7. Security Architecture
[Security controls, authentication, authorization, encryption, network isolation]

## 8. Scalability & Performance
[How the system scales, performance characteristics, bottlenecks addressed]

## 9. High Availability & Disaster Recovery
[HA strategy, redundancy, backup/restore, RTO/RPO targets]

## 10. Cost Considerations
[Cost drivers, optimization strategies, estimated monthly spend]

Return ONLY the markdown document (no code blocks, just raw markdown).
"""
        
        logger.info("Generating HLD document...")
        response = await self.doc_agent.run(prompt)
        markdown_content = getattr(response, "result", str(response))
        
        metadata = DocumentationMetadata(
            document_type="hld",
            generated_at=datetime.utcnow().isoformat(),
            diagram_services_count=len(nodes)
        )
        
        return {
            'markdown': markdown_content,
            'metadata': metadata.__dict__,
            'format': 'markdown'
        }
    
    async def generate_lld(
        self,
        diagram: Dict[str, Any],
        service_configs: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate Low-Level Design (LLD) document.
        
        Includes:
        - Detailed service specifications
        - Configuration parameters
        - SKU/tier selections with justification
        - Network topology details
        - Security configurations
        - Monitoring & alerting setup
        - Backup & recovery procedures
        
        Args:
            diagram: ReactFlow diagram
            service_configs: Optional detailed service configurations
            
        Returns:
            LLD document in markdown format
        """
        if not self.doc_agent:
            await self.initialize()
        
        nodes = diagram.get('nodes', [])
        
        prompt = f"""Generate a comprehensive Low-Level Design (LLD) document for this Azure architecture.

ARCHITECTURE DIAGRAM:
{json.dumps(diagram, indent=2)[:6000]}...

{f"SERVICE CONFIGURATIONS:\\n{json.dumps(service_configs, indent=2)[:3000]}" if service_configs else ""}

Create a detailed LLD with these sections:

# Low-Level Design Document

## 1. Service Specifications

[For EACH Azure service in the diagram, provide]:

### Service Name
- **Type**: [Azure service type]
- **SKU/Tier**: [Specific SKU with justification]
- **Region**: [Deployment region]
- **Configuration**:
  - Parameter 1: value
  - Parameter 2: value
- **Dependencies**: [List of dependent services]
- **Security**: [Access controls, encryption, private endpoints]
- **Monitoring**: [Metrics, alerts, diagnostic settings]

## 2. Network Architecture

### Virtual Networks
[VNet configurations, address spaces, subnets]

### Network Security Groups
[NSG rules for each subnet/service]

### Private Endpoints
[Private connectivity configurations]

### DNS Configuration
[Private DNS zones, custom DNS]

## 3. Identity & Access Management

### Managed Identities
[System/user-assigned identities for each service]

### RBAC Assignments
[Role assignments by scope and principal]

### Access Policies
[Key Vault, Storage, etc. access policies]

## 4. Data Architecture

### Storage Accounts
[Blob containers, file shares, tables, queues]

### Databases
[Schema overview, partitioning strategy, backup config]

### Data Lifecycle
[Retention policies, archival, deletion]

## 5. Monitoring & Logging

### Application Insights
[Telemetry collection, custom metrics]

### Log Analytics
[Log collection, retention, queries]

### Alerts
[Alert rules, action groups, notification channels]

## 6. Backup & Disaster Recovery

### Backup Configuration
[Backup policies, schedules, retention]

### Disaster Recovery
[Replication, failover procedures, RTO/RPO]

Return ONLY the markdown document.
"""
        
        logger.info("Generating LLD document...")
        response = await self.doc_agent.run(prompt)
        markdown_content = getattr(response, "result", str(response))
        
        metadata = DocumentationMetadata(
            document_type="lld",
            generated_at=datetime.utcnow().isoformat(),
            diagram_services_count=len(nodes)
        )
        
        return {
            'markdown': markdown_content,
            'metadata': metadata.__dict__,
            'format': 'markdown'
        }
    
    async def generate_runbook(
        self,
        diagram: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate operational runbook.
        
        Includes:
        - Startup/shutdown procedures
        - Health check procedures
        - Common troubleshooting scenarios
        - Incident response procedures
        - Maintenance procedures
        - Scaling procedures
        - Backup/restore procedures
        
        Args:
            diagram: ReactFlow diagram
            
        Returns:
            Runbook in markdown format
        """
        if not self.doc_agent:
            await self.initialize()
        
        prompt = f"""Generate an operational runbook for this Azure architecture.

ARCHITECTURE DIAGRAM:
{json.dumps(diagram, indent=2)[:5000]}...

Create a practical runbook with these sections:

# Operational Runbook

## 1. System Overview
[Brief description of what the system does and key components]

## 2. Startup Procedures

### Full System Startup
1. [Step-by-step startup sequence]
2. [Include dependencies and timing]
3. [Verification steps]

### Individual Service Startup
[For each critical service, provide startup procedure]

## 3. Shutdown Procedures

### Graceful Shutdown
1. [Step-by-step shutdown sequence]
2. [Data persistence checks]
3. [Verification steps]

### Emergency Shutdown
[Rapid shutdown procedure for emergencies]

## 4. Health Checks

### System Health
- Check 1: [How to verify + expected result]
- Check 2: [How to verify + expected result]

### Service Health
[For each service, describe health check procedure]

## 5. Troubleshooting

### Common Issues

#### Issue: [Description]
**Symptoms**: [What you observe]
**Diagnosis**: [How to confirm]
**Resolution**: [Step-by-step fix]

[Repeat for 5-10 common issues]

### Performance Issues
[How to diagnose and resolve performance problems]

### Connectivity Issues
[Network troubleshooting procedures]

## 6. Incident Response

### Critical Incident Procedure
1. [Immediate actions]
2. [Escalation criteria]
3. [Communication procedures]

### Data Loss Incident
[Specific procedures for data loss scenarios]

## 7. Maintenance Procedures

### Regular Maintenance
- Daily: [Tasks]
- Weekly: [Tasks]
- Monthly: [Tasks]

### Patching & Updates
[How to apply updates safely]

## 8. Scaling Procedures

### Scale Up
[Steps to increase capacity]

### Scale Down
[Steps to reduce capacity]

## 9. Backup & Recovery

### Backup Verification
[How to verify backups are working]

### Recovery Procedures
[Step-by-step restore from backup]

## 10. Monitoring & Alerts

### Key Metrics
[Critical metrics to monitor]

### Alert Response
[How to respond to each alert type]

Return ONLY the markdown document.
"""
        
        logger.info("Generating runbook...")
        response = await self.doc_agent.run(prompt)
        markdown_content = getattr(response, "result", str(response))
        
        metadata = DocumentationMetadata(
            document_type="runbook",
            generated_at=datetime.utcnow().isoformat(),
            diagram_services_count=len(diagram.get('nodes', []))
        )
        
        return {
            'markdown': markdown_content,
            'metadata': metadata.__dict__,
            'format': 'markdown'
        }
    
    async def generate_deployment_guide(
        self,
        diagram: Dict[str, Any],
        iac_code: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate deployment guide.
        
        Includes:
        - Prerequisites
        - Environment setup
        - Step-by-step deployment instructions
        - Post-deployment validation
        - Rollback procedures
        
        Args:
            diagram: ReactFlow diagram
            iac_code: Optional IaC code (Bicep/Terraform)
            
        Returns:
            Deployment guide in markdown format
        """
        if not self.doc_agent:
            await self.initialize()
        
        bicep_code = iac_code.get('bicep', {}).get('bicep_code', '') if iac_code else ''
        terraform_code = iac_code.get('terraform', {}).get('terraform_code', '') if iac_code else ''
        
        prompt = f"""Generate a comprehensive deployment guide for this Azure architecture.

ARCHITECTURE DIAGRAM:
{json.dumps(diagram, indent=2)[:4000]}...

{f"BICEP CODE:\\n```bicep\\n{bicep_code[:2000]}...\\n```\\n" if bicep_code else ""}
{f"TERRAFORM CODE:\\n```hcl\\n{terraform_code[:2000]}...\\n```\\n" if terraform_code else ""}

Create a practical deployment guide:

# Deployment Guide

## 1. Prerequisites

### Required Tools
- Azure CLI version X.X or later
- [Other tools needed]

### Required Permissions
- Azure subscription with Owner/Contributor role
- [Other permissions]

### Required Information
- Subscription ID
- Resource group name
- [Other parameters]

## 2. Environment Setup

### Step 1: Install Tools
```bash
# Commands to install required tools
```

### Step 2: Authenticate
```bash
# Azure authentication commands
```

### Step 3: Set Variables
```bash
# Environment variable setup
```

## 3. Deployment Steps

### Option A: Deploy with Bicep
```bash
# Step-by-step Bicep deployment commands
```

### Option B: Deploy with Terraform
```bash
# Step-by-step Terraform deployment commands
```

## 4. Post-Deployment Configuration

### Step 1: Verify Deployment
[How to verify each component deployed successfully]

### Step 2: Configure Services
[Post-deployment configuration steps]

### Step 3: Enable Monitoring
[Set up monitoring and alerts]

## 5. Validation & Testing

### Smoke Tests
[Quick tests to verify basic functionality]

### Integration Tests
[How to test service integrations]

## 6. Rollback Procedure

### Rollback Steps
[How to safely rollback if deployment fails]

## 7. Common Deployment Issues

### Issue: [Description]
**Solution**: [How to resolve]

[5-10 common deployment issues]

Return ONLY the markdown document.
"""
        
        logger.info("Generating deployment guide...")
        response = await self.doc_agent.run(prompt)
        markdown_content = getattr(response, "result", str(response))
        
        metadata = DocumentationMetadata(
            document_type="deployment_guide",
            generated_at=datetime.utcnow().isoformat(),
            diagram_services_count=len(diagram.get('nodes', []))
        )
        
        return {
            'markdown': markdown_content,
            'metadata': metadata.__dict__,
            'format': 'markdown'
        }


async def create_documentation_generator(agent_client) -> DocumentationGenerator:
    """
    Factory function to create and initialize DocumentationGenerator.
    
    Args:
        agent_client: Azure AI, OpenAI, or local model client
        
    Returns:
        Initialized DocumentationGenerator instance
    """
    generator = DocumentationGenerator(agent_client)
    await generator.initialize()
    return generator
