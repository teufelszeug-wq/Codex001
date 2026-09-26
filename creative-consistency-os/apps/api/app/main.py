from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.domain import Project
from app.services import ProjectService


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ProjectRead(BaseModel):
    id: UUID
    title: str
    schema_version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, project: Project) -> "ProjectRead":
        return cls(
            id=project.id,
            title=project.title,
            schema_version=project.schema_version,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

api = APIRouter(prefix=settings.api_prefix)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@api.get("/projects", response_model=list[ProjectRead], tags=["projects"])
def list_projects(session: Session = Depends(get_session)) -> list[ProjectRead]:
    return [ProjectRead.from_domain(project) for project in ProjectService(session).list_projects()]


@api.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED, tags=["projects"])
def create_project(payload: ProjectCreate, session: Session = Depends(get_session)) -> ProjectRead:
    try:
        project = ProjectService(session).create_project(payload.title)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return ProjectRead.from_domain(project)


@api.get("/projects/{project_id}", response_model=ProjectRead, tags=["projects"])
def get_project(project_id: UUID, session: Session = Depends(get_session)) -> ProjectRead:
    project = ProjectService(session).get_project(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectRead.from_domain(project)


app.include_router(api)
