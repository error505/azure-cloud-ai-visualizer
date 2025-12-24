# Enterprise Features API Reference

## 🎯 Quick Reference

All new enterprise features are available under the `/api` prefix.

### Base URL
```
Local Development: http://localhost:8000/api
Production: https://your-domain.com/api
```

---

## 📋 Table of Contents
1. [Validation Endpoints](#validation-endpoints)
2. [Autopilot Endpoints](#autopilot-endpoints)
3. [Compliance Endpoints](#compliance-endpoints)
4. [Documentation Endpoints](#documentation-endpoints)

---

## Validation Endpoints

### POST `/api/validation/requirements`
Validate new architecture from natural language requirements.

**Request:**
```json
{
  "requirements": "Build a secure e-commerce platform with payment processing and GDPR compliance"
}
```

**Response:**
```json
{
  "architect_proposal": {
    "architecture_description": "Proposed architecture with Azure services...",
    "rationale": "Security-first design with...",
    "cost_estimate": "$2,500-$3,000/month",
    "compliance_frameworks": ["PCI-DSS", "GDPR", "ISO 27001"]
  },
  "critic_review": {
    "overall_assessment": "Strong architecture with minor improvements needed",
    "strengths": ["Robust security", "Scalable design"],
    "issues": [
      {
        "category": "security",
        "severity": "high",
        "title": "Missing encryption at rest for storage account",
        "description": "Storage account should have encryption enabled",
        "recommendation": "Enable encryption at rest"
      }
    ],
    "summary": "7 issues identified (0 critical, 2 high, 3 medium, 2 low)"
  },
  "conflicts": [
    {
      "issue_id": "sec-001",
      "description": "Critical security gap in storage configuration"
    }
  ],
  "final_recommendation": {
    "status": "approve_with_changes",
    "score": 78,
    "action": "Address 2 high severity issues before deployment"
  },
  "auto_fix_available": true
}
```

---

### POST `/api/validation/diagram`
Audit existing diagram for issues.

**Request:**
```json
{
  "diagram": {
    "nodes": [...],
    "edges": [...]
  }
}
```

**Response:** Same as `/api/validation/requirements`

---

### POST `/api/validation/apply-fixes`
Apply automatic remediation fixes.

**Request:**
```json
{
  "diagram": {
    "nodes": [...],
    "edges": [...]
  },
  "selected_issue_ids": ["sec-001", "cost-003", "rel-002"]
}
```

**Response:**
```json
{
  "updated_diagram": {
    "nodes": [...],
    "edges": [...]
  },
  "fixes_applied": [
    {
      "issue_id": "sec-001",
      "action": "add_node",
      "description": "Added Key Vault for secret management"
    },
    {
      "issue_id": "cost-003",
      "action": "modify_node",
      "description": "Right-sized App Service from Premium to Standard"
    }
  ]
}
```

---

## Autopilot Endpoints

### POST `/api/autopilot/parse`
Parse natural language requirements into structured format.

**Request:**
```json
{
  "requirements": "Build a HIPAA-compliant healthcare data platform with real-time analytics, supporting 10,000 concurrent users, budget under $5,000/month"
}
```

**Response:**
```json
{
  "workload_type": "healthcare data platform",
  "services_needed": [
    "Azure SQL Database",
    "Azure Stream Analytics",
    "Azure Data Lake",
    "Application Insights"
  ],
  "compliance_frameworks": ["HIPAA", "ISO 27001"],
  "budget_constraint": "under $5,000/month",
  "performance_requirements": "support 10,000 concurrent users",
  "data_requirements": "real-time analytics",
  "scale_requirements": "10,000 concurrent users",
  "integration_requirements": null
}
```

---

### POST `/api/autopilot/generate`
Generate complete architecture from requirements.

**Request:**
```json
{
  "requirements": "Build a scalable e-commerce platform with payment processing",
  "use_parallel_pass": true
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "diagram": {
      "nodes": [
        {
          "id": "1",
          "type": "azureService",
          "data": {
            "label": "App Service",
            "serviceType": "App Service",
            "sku": "Standard S1",
            "region": "East US"
          }
        }
      ],
      "edges": [...]
    },
    "iac": {
      "bicep": "resource appService 'Microsoft.Web/sites@2022-03-01' = {...}",
      "terraform": "resource \"azurerm_app_service\" \"main\" {...}"
    },
    "cost_estimate": "$850-$1,200/month",
    "compliance": ["PCI-DSS", "ISO 27001"],
    "run_id": "run_abc123"
  }
}
```

---

## Compliance Endpoints

### GET `/api/compliance/frameworks`
List all available compliance frameworks.

**Response:**
```json
{
  "frameworks": [
    {
      "name": "ISO 27001",
      "description": "International standard for information security management",
      "requirements_count": 4
    },
    {
      "name": "SOC 2",
      "description": "Service organization controls for SaaS providers",
      "requirements_count": 3
    },
    {
      "name": "HIPAA",
      "description": "Healthcare data protection and privacy",
      "requirements_count": 3
    },
    {
      "name": "PCI-DSS",
      "description": "Payment card industry data security standard",
      "requirements_count": 3
    },
    {
      "name": "GDPR",
      "description": "EU General Data Protection Regulation",
      "requirements_count": 3
    }
  ]
}
```

---

### POST `/api/compliance/detect`
Auto-detect required compliance frameworks from diagram.

**Request:**
```json
{
  "diagram": {
    "nodes": [
      {
        "id": "1",
        "data": {
          "label": "Patient Database",
          "description": "Stores PHI data"
        }
      }
    ]
  }
}
```

**Response:**
```json
{
  "required_frameworks": ["HIPAA", "ISO 27001", "SOC 2"],
  "rationale": {
    "HIPAA": "Healthcare/PHI data detected in architecture",
    "ISO 27001": "General information security framework",
    "SOC 2": "Service organization controls for cloud services"
  }
}
```

---

### POST `/api/compliance/validate`
Validate diagram against compliance frameworks.

**Request:**
```json
{
  "diagram": {
    "nodes": [...],
    "edges": [...]
  },
  "frameworks": ["HIPAA", "PCI-DSS"]  // Optional, auto-detects if omitted
}
```

**Response:**
```json
{
  "frameworks": ["HIPAA", "PCI-DSS", "ISO 27001"],
  "overall_score": 72,
  "violations": [
    {
      "framework": "HIPAA",
      "requirement_id": "HIPAA-164.312(a)(2)(iv)",
      "title": "PHI Encryption",
      "description": "Protected Health Information must be encrypted at rest and in transit",
      "affected_services": ["storage-account-1", "sql-database-1"],
      "severity": "critical",
      "remediation": "Enable encryption at rest and configure TLS 1.2+",
      "auto_fixable": true
    }
  ],
  "compliant_controls": [
    "HIPAA: Access Logging",
    "PCI-DSS: Network Segmentation"
  ],
  "recommendations": [
    "Address 2 critical compliance violations immediately",
    "Ensure all PHI is encrypted and access is logged",
    "Enable diagnostic settings on all services for audit trail"
  ],
  "generated_at": "2025-01-15T10:30:00Z",
  "services_analyzed": 12
}
```

---

## Documentation Endpoints

### GET `/api/docs/types`
List all available document types.

**Response:**
```json
{
  "document_types": [
    {
      "type": "hld",
      "name": "High-Level Design",
      "description": "Executive summary, architecture overview, components, data flows, integrations, tech stack, security, scalability, HA/DR, cost considerations",
      "sections": 10
    },
    {
      "type": "lld",
      "name": "Low-Level Design",
      "description": "Detailed service specifications (SKU, config, dependencies), network architecture, IAM, data architecture, monitoring, backup/DR",
      "sections": 6
    },
    {
      "type": "runbook",
      "name": "Operational Runbook",
      "description": "Startup/shutdown procedures, health checks, troubleshooting guide, incident response, maintenance tasks, scaling procedures, backup/recovery, monitoring/alerts",
      "sections": 10
    },
    {
      "type": "deployment",
      "name": "Deployment Guide",
      "description": "Prerequisites, environment setup, deployment steps (Bicep/Terraform), post-deployment config, validation/testing, rollback procedures, common issues",
      "sections": 7
    }
  ]
}
```

---

### POST `/api/docs/generate`
Generate AI-powered documentation from diagram.

**Request:**
```json
{
  "diagram": {
    "nodes": [...],
    "edges": [...]
  },
  "doc_type": "hld",
  "architecture_description": "E-commerce platform with microservices architecture, supporting 50,000+ concurrent users with global distribution"
}
```

**Response:**
```json
{
  "success": true,
  "markdown": "# High-Level Design Document\n\n## Executive Summary\n\nThis document outlines...",
  "metadata": {
    "document_type": "hld",
    "generated_at": "2025-01-15T10:30:00Z",
    "diagram_services_count": 15,
    "version": "1.0.0"
  },
  "format": "markdown"
}
```

**Sample HLD Output:**
```markdown
# High-Level Design Document

## 1. Executive Summary
This architecture implements a scalable e-commerce platform...

## 2. System Architecture Overview
The system follows a microservices architecture pattern...

## 3. Components
### Frontend Layer
- **App Service (Web)**: React SPA, Standard S1, East US
  - Purpose: User interface
  - Responsibilities: Product browsing, checkout flow
  - Features: Auto-scaling, SSL, CDN integration

### Application Layer
- **App Service (API)**: .NET Core API, Standard S2, East US
  - Purpose: Business logic orchestration
  - Responsibilities: Order processing, inventory management
  
[... 8 more sections ...]
```

---

## 🔐 Authentication

All endpoints support Azure AD authentication (optional):

```bash
Authorization: Bearer <azure_ad_token>
```

For development, authentication can be disabled in `.env`:

```bash
DISABLE_AUTH=true
```

---

## 🚨 Error Responses

All endpoints return consistent error format:

```json
{
  "detail": "Compliance validation failed: Invalid diagram format"
}
```

**HTTP Status Codes:**
- `200`: Success
- `400`: Bad Request (invalid input)
- `401`: Unauthorized (missing/invalid auth)
- `500`: Internal Server Error

---

## 🔥 Health Check Endpoints

Check service availability:

```bash
GET /api/validation/health     → {"status": "healthy", "service": "validation"}
GET /api/autopilot/health      → {"status": "healthy", "service": "autopilot"}
GET /api/compliance/health     → {"status": "healthy", "service": "compliance"}
GET /api/docs/health           → {"status": "healthy", "service": "documentation"}
```

---

## 🧪 Testing Examples

### Using cURL

**Validate Requirements:**
```bash
curl -X POST http://localhost:8000/api/validation/requirements \
  -H "Content-Type: application/json" \
  -d '{
    "requirements": "Build a HIPAA-compliant data warehouse"
  }'
```

**Generate Documentation:**
```bash
curl -X POST http://localhost:8000/api/docs/generate \
  -H "Content-Type: application/json" \
  -d '{
    "diagram": {...},
    "doc_type": "hld",
    "architecture_description": "Healthcare data platform"
  }'
```

**Validate Compliance:**
```bash
curl -X POST http://localhost:8000/api/compliance/validate \
  -H "Content-Type: application/json" \
  -d '{
    "diagram": {...},
    "frameworks": ["HIPAA", "ISO 27001"]
  }'
```

---

### Using Fetch API (Frontend)

```typescript
// Validate requirements
const response = await fetch('/api/validation/requirements', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ requirements: 'Build a secure platform' })
});
const validation = await response.json();

// Generate autopilot architecture
const autopilot = await fetch('/api/autopilot/generate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ 
    requirements: 'E-commerce with payment processing',
    use_parallel_pass: true 
  })
});
const architecture = await autopilot.json();

// Check compliance
const compliance = await fetch('/api/compliance/validate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ 
    diagram: currentDiagram,
    frameworks: ['PCI-DSS', 'GDPR']
  })
});
const report = await compliance.json();

// Generate documentation
const docs = await fetch('/api/docs/generate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    diagram: currentDiagram,
    doc_type: 'runbook',
    architecture_description: 'Microservices platform'
  })
});
const documentation = await docs.json();
```

---

## 📊 Rate Limits

No rate limits currently enforced. Recommended limits for production:

- `/api/validation/*`: 100 requests/minute
- `/api/autopilot/*`: 20 requests/minute (computationally expensive)
- `/api/compliance/*`: 100 requests/minute
- `/api/docs/*`: 50 requests/minute

---

## 🎯 Next Steps

1. Implement frontend components to consume these APIs
2. Add authentication middleware
3. Set up rate limiting
4. Add request/response logging
5. Create OpenAPI/Swagger documentation

---

*API Version: 1.0*  
*Last Updated: 2025-01-XX*
