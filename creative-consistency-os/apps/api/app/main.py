from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.domain import Project, WorldBuilderProfile
from app.services import ProjectService, WorldBuilderService


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


class CustomGenreInput(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    weight: int = Field(default=50, ge=0, le=100)


class WorldBuilderWrite(BaseModel):
    setup_mode: str
    selected_genres: list[str] = Field(default_factory=list)
    genre_weights: dict[str, int] = Field(default_factory=dict)
    custom_genres: list[CustomGenreInput] = Field(default_factory=list)
    section_modes: dict[str, str] = Field(default_factory=dict)
    section_notes: dict[str, str] = Field(default_factory=dict)
    import_format: str | None = None
    import_notes: str | None = Field(default=None, max_length=2000)
    status: str = "configured"


class WorldBuilderRead(BaseModel):
    project_id: UUID
    setup_mode: str
    selected_genres: list[str]
    genre_weights: dict[str, int]
    custom_genres: list[dict[str, object]]
    section_modes: dict[str, str]
    section_notes: dict[str, str]
    import_format: str | None
    import_notes: str | None
    status: str
    recommendations: dict[str, dict[str, object]]
    wizard_version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, profile: WorldBuilderProfile) -> "WorldBuilderRead":
        return cls(
            project_id=profile.project_id,
            setup_mode=profile.setup_mode,
            selected_genres=profile.selected_genres,
            genre_weights=profile.genre_weights,
            custom_genres=profile.custom_genres,
            section_modes=profile.section_modes,
            section_notes=profile.section_notes,
            import_format=profile.import_format,
            import_notes=profile.import_notes,
            status=profile.status,
            recommendations=profile.recommendations,
            wizard_version=profile.wizard_version,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )


app = FastAPI(title=settings.app_name, version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "OPTIONS"],
    allow_headers=["*"],
)

api = APIRouter(prefix=settings.api_prefix)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@api.get("/catalog/world-builder", tags=["world-builder"])
def world_builder_catalog() -> dict[str, object]:
    return WorldBuilderService.catalog()


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


@api.get("/projects/{project_id}/world-builder", response_model=WorldBuilderRead, tags=["world-builder"])
def get_world_builder(project_id: UUID, session: Session = Depends(get_session)) -> WorldBuilderRead:
    try:
        profile = WorldBuilderService(session).get_profile(project_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="World Builder profile not found")
    return WorldBuilderRead.from_domain(profile)


@api.put("/projects/{project_id}/world-builder", response_model=WorldBuilderRead, tags=["world-builder"])
def save_world_builder(
    project_id: UUID,
    payload: WorldBuilderWrite,
    session: Session = Depends(get_session),
) -> WorldBuilderRead:
    try:
        profile = WorldBuilderService(session).save_profile(
            project_id,
            setup_mode=payload.setup_mode,
            selected_genres=payload.selected_genres,
            genre_weights=payload.genre_weights,
            custom_genres=[item.model_dump() for item in payload.custom_genres],
            section_modes=payload.section_modes,
            section_notes=payload.section_notes,
            import_format=payload.import_format,
            import_notes=payload.import_notes,
            status=payload.status,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return WorldBuilderRead.from_domain(profile)


app.include_router(api)
