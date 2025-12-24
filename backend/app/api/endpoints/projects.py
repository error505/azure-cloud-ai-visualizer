"""Project management endpoints."""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Depends, Body
from pydantic import BaseModel

from app.core.azure_client import AzureClientManager
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


class ProjectCreate(BaseModel):
    """Project creation request model."""
    name: str
    description: str = ""
    diagram_data: Dict[str, Any] = {}


class ProjectUpdate(BaseModel):
    """Project update request model."""
    name: str | None = None
    description: str | None = None
    diagram_data: Dict[str, Any] | None = None


class ProjectResponse(BaseModel):
    """Project response model."""
    id: str
    name: str
    description: str
    diagram_data: Dict[str, Any]
    share_token: str | None = None
    created_at: datetime
    updated_at: datetime


class ShareLinkResponse(BaseModel):
    """Shareable link response model."""
    share_token: str
    share_url: str


def get_azure_clients(request: Request) -> AzureClientManager:
    """Dependency to get Azure clients from app state."""
    return request.app.state.azure_clients


def _build_share_url(project_id: str, share_token: str) -> str:
    """Build a shareable workspace URL using configured frontend base."""
    base = settings.FRONTEND_BASE_URL.rstrip("/") if settings.FRONTEND_BASE_URL else "http://localhost:8080/app"
    url = f"{base}/{project_id}"
    if share_token:
        url = f"{url}?share_token={share_token}"
    return url


@router.post("/", response_model=ProjectResponse)
async def create_project(
    project: ProjectCreate,
    azure_clients: AzureClientManager = Depends(get_azure_clients)
) -> ProjectResponse:
    """Create a new project."""
    try:
        project_id = str(uuid4())
        now = datetime.utcnow()
        
        project_data = {
            "id": project_id,
            "name": project.name,
            "description": project.description,
            "diagram_data": project.diagram_data,
            "share_token": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        
        # Save to blob storage
        blob_client = azure_clients.get_blob_client()
        container_name = settings.AZURE_STORAGE_CONTAINER_NAME_PROJECTS
        blob_name = f"{project_id}/project.json"
        
        blob_data = json.dumps(project_data, indent=2)
        await blob_client.get_blob_client(
            container=container_name, 
            blob=blob_name
        ).upload_blob(blob_data, overwrite=True)
        
        logger.info(f"Created project {project_id}: {project.name}")
        return ProjectResponse(**project_data)
        
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    azure_clients: AzureClientManager = Depends(get_azure_clients)
) -> ProjectResponse:
    """Get a project by ID."""
    try:
        blob_client = azure_clients.get_blob_client()
        container_name = settings.AZURE_STORAGE_CONTAINER_NAME_PROJECTS
        blob_name = f"{project_id}/project.json"
        
        blob_data = await blob_client.get_blob_client(
            container=container_name,
            blob=blob_name
        ).download_blob()
        
        project_data = json.loads(await blob_data.readall())
        return ProjectResponse(**project_data)
        
    except Exception as e:
        logger.error(f"Failed to get project {project_id}: {e}")
        raise HTTPException(status_code=404, detail="Project not found")


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    project_update: ProjectUpdate,
    azure_clients: AzureClientManager = Depends(get_azure_clients)
) -> ProjectResponse:
    """Update a project."""
    try:
        # First get the existing project
        existing_project = await get_project(project_id, azure_clients)
        
        # Update fields
        updated_data = existing_project.dict()
        if project_update.name is not None:
            updated_data["name"] = project_update.name
        if project_update.description is not None:
            updated_data["description"] = project_update.description
        if project_update.diagram_data is not None:
            updated_data["diagram_data"] = project_update.diagram_data
        
        updated_data["updated_at"] = datetime.utcnow().isoformat()
        
        # Save back to blob storage
        blob_client = azure_clients.get_blob_client()
        container_name = settings.AZURE_STORAGE_CONTAINER_NAME_PROJECTS
        blob_name = f"{project_id}/project.json"
        
        blob_data = json.dumps(updated_data, indent=2)
        await blob_client.get_blob_client(
            container=container_name,
            blob=blob_name
        ).upload_blob(blob_data, overwrite=True)
        
        logger.info(f"Updated project {project_id}")
        return ProjectResponse(**updated_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update project: {str(e)}")


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    azure_clients: AzureClientManager = Depends(get_azure_clients)
) -> Dict[str, str]:
    """Delete a project."""
    try:
        blob_client = azure_clients.get_blob_client()
        container_name = settings.AZURE_STORAGE_CONTAINER_NAME_PROJECTS
        
        # Delete the project blob
        blob_name = f"{project_id}/project.json"
        await blob_client.get_blob_client(
            container=container_name,
            blob=blob_name
        ).delete_blob()
        
        logger.info(f"Deleted project {project_id}")
        return {"message": "Project deleted successfully"}
        
    except Exception as e:
        logger.error(f"Failed to delete project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")


@router.get("/", response_model=List[ProjectResponse])
async def list_projects(
    azure_clients: AzureClientManager = Depends(get_azure_clients)
) -> List[ProjectResponse]:
    """List all projects."""
    try:
        blob_client = azure_clients.get_blob_client()
        container_name = settings.AZURE_STORAGE_CONTAINER_NAME_PROJECTS
        
        projects = []
        async for blob in blob_client.get_container_client(container_name).list_blobs():
            if blob.name.endswith("/project.json"):
                try:
                    blob_data = await blob_client.get_blob_client(
                        container=container_name,
                        blob=blob.name
                    ).download_blob()
                    
                    project_data = json.loads(await blob_data.readall())
                    projects.append(ProjectResponse(**project_data))
                except Exception as e:
                    logger.warning(f"Failed to load project from {blob.name}: {e}")
                    continue
        
        # Sort by updated_at descending
        projects.sort(key=lambda p: p.updated_at, reverse=True)
        return projects
        
    except Exception as e:
        logger.error(f"Failed to list projects: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list projects: {str(e)}")


@router.post("/{project_id}/share", response_model=ShareLinkResponse)
async def create_share_link(
    project_id: str,
    project_update: ProjectUpdate | None = Body(None),
    azure_clients: AzureClientManager = Depends(get_azure_clients)
) -> ShareLinkResponse:
    """Create or rotate a shareable link for a project."""
    try:
        # Fetch the existing project
        project = await get_project(project_id, azure_clients)
        project_data = project.dict()

        # If the caller provided a diagram payload in the request body (frontend can
        # include the current diagram state when requesting a share link), merge
        # it into the blob we will write so the share contains the latest diagram.
        if project_update and project_update.diagram_data is not None:
            project_data["diagram_data"] = project_update.diagram_data

        share_token = uuid4().hex
        project_data["share_token"] = share_token
        project_data["updated_at"] = datetime.utcnow().isoformat()

        blob_client = azure_clients.get_blob_client()
        container_name = settings.AZURE_STORAGE_CONTAINER_NAME_PROJECTS
        blob_name = f"{project_id}/project.json"

        blob_data = json.dumps(project_data, indent=2)
        await blob_client.get_blob_client(
            container=container_name,
            blob=blob_name
        ).upload_blob(blob_data, overwrite=True)

        logger.info(f"Generated share link for project {project_id}")
        return ShareLinkResponse(
            share_token=share_token,
            share_url=_build_share_url(project_id, share_token),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create share link for project {project_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create share link: {str(e)}")


@router.get("/share/{share_token}", response_model=ProjectResponse)
async def get_project_by_share_token(
    share_token: str,
    azure_clients: AzureClientManager = Depends(get_azure_clients)
) -> ProjectResponse:
    """Resolve a project by its share token."""
    try:
        blob_client = azure_clients.get_blob_client()
        container_name = settings.AZURE_STORAGE_CONTAINER_NAME_PROJECTS

        # Iterate project manifests to find matching token. This is linear but
        # acceptable for modest project counts; can be optimized with an index later.
        async for blob in blob_client.get_container_client(container_name).list_blobs():
            if not blob.name.endswith("/project.json"):
                continue
            try:
                blob_data = await blob_client.get_blob_client(
                    container=container_name,
                    blob=blob.name
                ).download_blob()
                project_data = json.loads(await blob_data.readall())
                if project_data.get("share_token") == share_token:
                    return ProjectResponse(**project_data)
            except Exception as inner_exc:
                logger.warning(f"Failed to inspect project blob {blob.name}: {inner_exc}")
                continue

        raise HTTPException(status_code=404, detail="Share link not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resolve share token: {e}")
        raise HTTPException(status_code=500, detail="Failed to resolve share link")
