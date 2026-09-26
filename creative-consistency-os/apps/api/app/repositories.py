import json
from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain import Project
from app.models import ChangeLogModel, ProjectModel


class ProjectRepository(ABC):
    @abstractmethod
    def list(self) -> list[Project]: ...

    @abstractmethod
    def get(self, project_id: UUID) -> Project | None: ...

    @abstractmethod
    def create(self, title: str) -> Project: ...


class SqlAlchemyProjectRepository(ProjectRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[Project]:
        rows = self.session.scalars(select(ProjectModel).order_by(ProjectModel.updated_at.desc())).all()
        return [self._to_domain(row) for row in rows]

    def get(self, project_id: UUID) -> Project | None:
        row = self.session.get(ProjectModel, str(project_id))
        return self._to_domain(row) if row else None

    def create(self, title: str) -> Project:
        row = ProjectModel(title=title.strip())
        self.session.add(row)
        self.session.flush()
        return self._to_domain(row)

    @staticmethod
    def _to_domain(row: ProjectModel) -> Project:
        return Project(
            id=UUID(row.id),
            title=row.title,
            schema_version=row.schema_version,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class ChangeLogRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_project_created(self, project_id: UUID, title: str) -> None:
        self.session.add(
            ChangeLogModel(
                project_id=str(project_id),
                event_type="PROJECT_CREATED",
                entity_type="Project",
                entity_id=str(project_id),
                before_json=None,
                after_json=json.dumps({"title": title}, ensure_ascii=False),
                reason="M1 project creation",
            )
        )
