"""Simple mock endpoints for testing."""

import logging
from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory storage for testing
projects_storage = {}


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


@router.post("/", response_model=ProjectResponse)
async def create_project(project: ProjectCreate) -> ProjectResponse:
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
            "created_at": now,
            "updated_at": now,
        }
        
        projects_storage[project_id] = project_data
        logger.info(f"Created project {project_id}: {project.name}")
        return ProjectResponse(**project_data)
        
    except Exception as e:
        logger.error(f"Failed to create project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create project: {str(e)}")


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str) -> ProjectResponse:
    """Get a project by ID."""
    if project_id not in projects_storage:
        raise HTTPException(status_code=404, detail="Project not found")
    
    return ProjectResponse(**projects_storage[project_id])


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(project_id: str, project_update: ProjectUpdate) -> ProjectResponse:
    """Update a project."""
    if project_id not in projects_storage:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project_data = projects_storage[project_id].copy()
    
    if project_update.name is not None:
        project_data["name"] = project_update.name
    if project_update.description is not None:
        project_data["description"] = project_update.description
    if project_update.diagram_data is not None:
        project_data["diagram_data"] = project_update.diagram_data
    
    project_data["updated_at"] = datetime.utcnow()
    projects_storage[project_id] = project_data
    
    logger.info(f"Updated project {project_id}")
    return ProjectResponse(**project_data)


@router.delete("/{project_id}")
async def delete_project(project_id: str) -> Dict[str, str]:
    """Delete a project."""
    if project_id not in projects_storage:
        raise HTTPException(status_code=404, detail="Project not found")
    
    del projects_storage[project_id]
    logger.info(f"Deleted project {project_id}")
    return {"message": "Project deleted successfully"}


def _build_share_url(project_id: str, share_token: str) -> str:
    """Build a shareable workspace URL using configured frontend base."""
    base = settings.FRONTEND_BASE_URL.rstrip("/") if settings.FRONTEND_BASE_URL else "http://localhost:8080/app"
    url = f"{base}/{project_id}"
    if share_token:
        url = f"{url}?share_token={share_token}"
    return url


@router.post("/{project_id}/share", response_model=ShareLinkResponse)
async def create_share_link(project_id: str) -> ShareLinkResponse:
    """Create or rotate a shareable link for a project."""
    if project_id not in projects_storage:
        # If the project was created elsewhere (e.g., Supabase), provision a placeholder
        now = datetime.utcnow()
        projects_storage[project_id] = {
            "id": project_id,
            "name": f"Project {project_id[:8]}",
            "description": "",
            "diagram_data": {},
            "share_token": None,
            "created_at": now,
            "updated_at": now,
        }

    share_token = uuid4().hex
    project_data = projects_storage[project_id]
    project_data["share_token"] = share_token
    project_data["updated_at"] = datetime.utcnow()
    projects_storage[project_id] = project_data

    return ShareLinkResponse(
        share_token=share_token,
        share_url=_build_share_url(project_id, share_token),
    )


@router.get("/share/{share_token}", response_model=ProjectResponse)
async def get_project_by_share_token(share_token: str) -> ProjectResponse:
    """Resolve a project by its share token (view-only collaboration entry point)."""
    for project in projects_storage.values():
        if project.get("share_token") == share_token:
            return ProjectResponse(**project)
    raise HTTPException(status_code=404, detail="Share link not found")


@router.get("/", response_model=List[ProjectResponse])
async def list_projects() -> List[ProjectResponse]:
    """List all projects."""
    projects = [ProjectResponse(**data) for data in projects_storage.values()]
    projects.sort(key=lambda p: p.updated_at, reverse=True)
    return projects
