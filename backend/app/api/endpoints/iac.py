"""IaC endpoints (thin router).

Delegates Bicep and Terraform generation to the modular generators in
`app.iac_generators`. The generators are AI-first and may fall back to
deterministic module implementations when agent convenience wrappers are
not available.
"""

from datetime import datetime
import json
import logging
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from app.core.azure_client import AzureClientManager
from app.iac_generators import generate_bicep_code, generate_terraform_code
from app.iac_generators.validation import validate_iac_with_cli
from app.iac_generators.enrichment import enrich_diagram_with_governance
from app.iac_generators.aws_migration import migrate_aws_diagram
from app.iac_generators.gcp_migration import migrate_gcp_diagram

logger = logging.getLogger(__name__)
router = APIRouter()


class IaCGenerateRequest(BaseModel):
    diagram_data: Dict[str, Any]
    target_format: str = "bicep"
    include_monitoring: bool = True
    include_security: bool = True
    resource_naming_convention: str = "standard"
    use_model: bool = False
    service_configs: Optional[Dict[str, Any]] = None
    # Optional: automatically deploy the generated IaC
    auto_deploy: bool = False
    deploy_resource_group: Optional[str] = None
    deploy_subscription_id: Optional[str] = None
    deploy_validation_only: bool = False

    # Terraform-specific options
    provider_version: Optional[str] = None
    required_providers: Optional[str] = None
    variables: Optional[str] = None
    remote_backend: Optional[str] = None
    workspace: Optional[str] = None
    init_and_validate: bool = False


class IaCResponse(BaseModel):
    id: str
    format: str
    content: str
    parameters: Dict[str, Any]
    created_at: datetime
    project_id: Optional[str] = None


def get_azure_clients(request: Request) -> AzureClientManager:
    return request.app.state.azure_clients


@router.post('/generate', response_model=IaCResponse)
async def generate_iac(
    request_data: IaCGenerateRequest,
    project_id: Optional[str] = None,
    azure_clients: AzureClientManager = Depends(get_azure_clients),
) -> IaCResponse:
    """Generate IaC (Bicep or Terraform) using AI-first generators.

    The endpoint returns a structured response with the generated code and
    any metadata/parameters the generator produced. Optionally runs CLI
    validation when `init_and_validate` is True.
    """
    try:
        try:
            agent = azure_clients.get_azure_architect_agent()
        except RuntimeError as re:
            # Provide a clearer HTTP error when the backend agent isn't initialized.
            logger.error('Azure Architect Agent unavailable: %s', re)
            raise HTTPException(
                status_code=503,
                detail=(
                    'AI agent not initialized. Ensure the backend was started with either Azure credentials '
                    'or OpenAI fallback enabled (set USE_OPENAI_FALLBACK=true and provide OPENAI_API_KEY). '
                    'See backend/README.md for OpenAI fallback instructions.'
                ),
            )
        diagram = request_data.diagram_data if isinstance(request_data.diagram_data, dict) else {}
        diagram, preflight = enrich_diagram_with_governance(diagram)
        
        # Try both AWS and GCP migrations
        aws_migration = migrate_aws_diagram(diagram)
        gcp_migration = migrate_gcp_diagram(diagram)
        
        # Use whichever migration was applied (AWS takes precedence if both detected)
        migration = aws_migration if aws_migration.applied else gcp_migration
        diagram = migration.diagram
        
        target = (request_data.target_format or 'bicep').lower()

        if target == 'bicep':
            result = await generate_bicep_code(agent, diagram, use_model=request_data.use_model)
            code_key = 'bicep_code'
        elif target == 'terraform':
            opts = {
                'provider_version': request_data.provider_version,
                'required_providers': request_data.required_providers,
                'variables': request_data.variables,
                'remote_backend': request_data.remote_backend,
                'workspace': request_data.workspace,
            }
            result = await generate_terraform_code(agent, diagram, options=opts, use_model=request_data.use_model)
            code_key = 'terraform_code'
        else:
            raise HTTPException(status_code=400, detail='Unsupported target format')

        content = ''
        parameters: Dict[str, Any] = {}
        if isinstance(result, dict):
            content = result.get(code_key, '') or ''
            parameters = result.get('parameters', {}) or {}
        else:
            content = str(result)
            parameters = {}

        if migration.applied or migration.unmapped_services:
            migration_key = 'aws_migration' if aws_migration.applied else 'gcp_migration'
            migration_payload = {
                'converted_nodes': migration.converted_nodes,
                'price_summary': migration.price_summary,
                'cost_summary': migration.cost_summary,
                'bicep_snippets': migration.bicep_snippets,
                'unmapped_services': migration.unmapped_services,
                'azure_diagram': migration.diagram,
            }
            parameters.setdefault(migration_key, {}).update(migration_payload)

        if preflight:
            parameters.setdefault('preflight', {})
            parameters['preflight'].update(preflight)

        # Optional CLI validation
        if request_data.init_and_validate:
            extra_files = {}
            if request_data.remote_backend:
                extra_files['backend.tf'] = request_data.remote_backend
            if request_data.variables:
                extra_files['variables.tf'] = request_data.variables
            validation = validate_iac_with_cli(target, content or '', extra_files)
            parameters.setdefault('validation', {})
            parameters['validation'].update(validation)

        iac_id = str(uuid4())
        now = datetime.utcnow()

        # Persist to blob if project specified (best-effort)
        if project_id:
            try:
                blob_client = azure_clients.get_blob_client()
                container_name = 'iac'
                blob_name = f"{project_id}/{iac_id}/{target}_template"
                iac_data = {
                    'id': iac_id,
                    'content': content,
                    'parameters': parameters,
                    'format': target,
                    'created_at': now.isoformat(),
                    'project_id': project_id,
                    'generation_request': request_data.dict()
                }
                await blob_client.get_blob_client(container=container_name, blob=blob_name).upload_blob(json.dumps(iac_data, indent=2), overwrite=True)
            except Exception:
                logger.exception('Failed to save generated IaC to blob storage')

        # Optional: auto-deploy the generated IaC (calls internal deployment handler)
        if request_data.auto_deploy:
            try:
                # Require deploy target params
                if not request_data.deploy_resource_group or not request_data.deploy_subscription_id:
                    parameters.setdefault('deployment', {})
                    parameters['deployment']['error'] = 'deploy_resource_group and deploy_subscription_id are required for auto_deploy'
                else:
                    from app.api.endpoints import deployment as deployment_api

                    dep_req = deployment_api.DeploymentRequest(
                        resource_group=request_data.deploy_resource_group,
                        subscription_id=request_data.deploy_subscription_id,
                        template_content=content or '',
                        template_format=target,
                        parameters=parameters,
                        validation_only=request_data.deploy_validation_only,
                    )

                    # Call the internal create_deployment handler
                    dep_resp = await deployment_api.create_deployment(dep_req, project_id, azure_clients)
                    parameters.setdefault('deployment', {})
                    parameters['deployment']['id'] = getattr(dep_resp, 'id', None)
                    parameters['deployment']['status'] = getattr(dep_resp, 'status', None)
            except Exception as e:
                logger.exception('Auto-deploy failed: %s', e)
                parameters.setdefault('deployment', {})
                parameters['deployment']['error'] = str(e)

        return IaCResponse(id=iac_id, format=target, content=content or '', parameters=parameters or {}, created_at=now, project_id=project_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Failed to generate IaC: %s', e)
        raise HTTPException(status_code=500, detail=f'Failed to generate IaC: {str(e)}')
