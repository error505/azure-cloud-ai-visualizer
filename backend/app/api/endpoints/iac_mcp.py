"""MCP-enhanced IaC generation endpoints."""

import json
import logging
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from app.core.azure_client import AzureClientManager
from app.iac_generators.aws_migration import migrate_aws_diagram

logger = logging.getLogger(__name__)
router = APIRouter()


class MCPIaCRequest(BaseModel):
    """MCP IaC generation request model."""
    diagram: Dict[str, Any]
    region: str = "westeurope"
    validate_output: bool = True


class MCPTerraformRequest(BaseModel):
    """MCP Terraform generation request model."""
    diagram: Dict[str, Any]
    provider: str = "azurerm"
    validate_output: bool = True


class MCPIaCResponse(BaseModel):
    """MCP IaC generation response model."""
    id: str
    bicep_code: str
    parameters: Dict[str, Any]
    validation: Dict[str, Any] = {}
    created_at: datetime
    mcp_enhanced: bool = True


class MCPTerraformResponse(BaseModel):
    """MCP Terraform generation response model."""
    id: str
    terraform_code: str
    variables: Dict[str, Any] = {}
    outputs: Dict[str, Any] = {}
    parameters: Dict[str, Any]
    validation: Dict[str, Any] = {}
    created_at: datetime
    mcp_enhanced: bool = True


def get_azure_clients(request: Request) -> AzureClientManager:
    return request.app.state.azure_clients


@router.post("/generate", response_model=MCPIaCResponse)
async def generate_iac_mcp(
    request_data: MCPIaCRequest,
    azure_clients: AzureClientManager = Depends(get_azure_clients),
) -> MCPIaCResponse:
    """Generate IaC using MCP-enhanced Azure Bicep tools."""
    try:
        agent = azure_clients.get_azure_architect_agent()
        migration = migrate_aws_diagram(request_data.diagram)
        diagram = migration.diagram
        
        # Generate Bicep using MCP enhancement
        result = await agent.generate_bicep_via_mcp(
            diagram=diagram,
            region=request_data.region
        )
        
        bicep_code = result.get("bicep_code", "")
        parameters = result.get("parameters", {}) or {}
        if migration.applied or migration.unmapped_services:
            migration_payload = {
                "converted_nodes": migration.converted_nodes,
                "price_summary": migration.price_summary,
                "cost_summary": migration.cost_summary,
                "bicep_snippets": migration.bicep_snippets,
                "unmapped_services": migration.unmapped_services,
                "azure_diagram": migration.diagram,
            }
            parameters.setdefault("aws_migration", {}).update(migration_payload)
        
        # Optional validation using MCP
        validation = {}
        if request_data.validate_output and bicep_code:
            try:
                validation = await agent.validate_bicep_with_mcp(bicep_code)
            except Exception as e:
                logger.warning(f"MCP validation failed: {e}")
                validation = {"valid": False, "errors": [f"Validation error: {str(e)}"]}
        
        iac_id = str(uuid4())
        now = datetime.utcnow()
        
        return MCPIaCResponse(
            id=iac_id,
            bicep_code=bicep_code,
            parameters=parameters,
            validation=validation,
            created_at=now,
            mcp_enhanced=True
        )
        
    except Exception as e:
        logger.exception(f"MCP IaC generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"MCP IaC generation failed: {str(e)}")


@router.post("/validate")
async def validate_bicep_mcp(
    bicep_code: str,
    azure_clients: AzureClientManager = Depends(get_azure_clients),
) -> Dict[str, Any]:
    """Validate Bicep code using MCP tools."""
    try:
        agent = azure_clients.get_azure_architect_agent()
        validation = await agent.validate_bicep_with_mcp(bicep_code)
        return validation
        
    except Exception as e:
        logger.exception(f"MCP Bicep validation failed: {e}")
        return {
            "valid": False,
            "errors": [f"Validation failed: {str(e)}"],
            "warnings": []
        }


@router.post("/terraform/generate", response_model=MCPTerraformResponse)
async def generate_terraform_mcp(
    request_data: MCPTerraformRequest,
    azure_clients: AzureClientManager = Depends(get_azure_clients),
) -> MCPTerraformResponse:
    """Generate Terraform using MCP-enhanced HashiCorp tools."""
    try:
        agent = azure_clients.get_azure_architect_agent()
        migration = migrate_aws_diagram(request_data.diagram)
        diagram = migration.diagram
        
        # Generate Terraform using MCP enhancement
        result = await agent.generate_terraform_via_mcp(
            diagram=diagram,
            provider=request_data.provider
        )
        
        terraform_code = result.get("terraform_code", "")
        variables = result.get("variables", {})
        outputs = result.get("outputs", {})
        parameters = result.get("parameters", {"provider": request_data.provider}) or {"provider": request_data.provider}
        if migration.applied or migration.unmapped_services:
            migration_payload = {
                "converted_nodes": migration.converted_nodes,
                "price_summary": migration.price_summary,
                "bicep_snippets": migration.bicep_snippets,
                "unmapped_services": migration.unmapped_services,
                "azure_diagram": migration.diagram,
            }
            parameters.setdefault("aws_migration", {}).update(migration_payload)
        
        # Optional validation using MCP
        validation = {}
        if request_data.validate_output and terraform_code:
            try:
                validation = await agent.validate_terraform_with_mcp(
                    terraform_code, 
                    provider=request_data.provider
                )
            except Exception as e:
                logger.warning(f"MCP Terraform validation failed: {e}")
                validation = {"valid": False, "errors": [f"Validation error: {str(e)}"]}
        
        iac_id = str(uuid4())
        now = datetime.utcnow()
        
        return MCPTerraformResponse(
            id=iac_id,
            terraform_code=terraform_code,
            variables=variables,
            outputs=outputs,
            parameters=parameters,
            validation=validation,
            created_at=now,
            mcp_enhanced=True
        )
        
    except Exception as e:
        logger.exception(f"MCP Terraform generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"MCP Terraform generation failed: {str(e)}")


@router.post("/terraform/validate")
async def validate_terraform_mcp(
    terraform_code: str,
    provider: str = "azurerm",
    azure_clients: AzureClientManager = Depends(get_azure_clients),
) -> Dict[str, Any]:
    """Validate Terraform code using MCP tools."""
    try:
        agent = azure_clients.get_azure_architect_agent()
        validation = await agent.validate_terraform_with_mcp(terraform_code, provider=provider)
        return validation
        
    except Exception as e:
        logger.exception(f"MCP Terraform validation failed: {e}")
        return {
            "valid": False,
            "errors": [f"Validation failed: {str(e)}"],
            "warnings": []
        }


@router.get("/terraform/provider/{provider}")
async def get_terraform_provider_info(
    provider: str,
    azure_clients: AzureClientManager = Depends(get_azure_clients),
) -> Dict[str, Any]:
    """Get Terraform provider information using MCP tools."""
    try:
        agent = azure_clients.get_azure_architect_agent()
        provider_info = await agent.get_terraform_provider_info_via_mcp(provider=provider)
        return provider_info
        
    except Exception as e:
        logger.exception(f"MCP provider info lookup failed: {e}")
        return {
            "error": f"Provider info lookup failed: {str(e)}",
            "provider": provider
        }
