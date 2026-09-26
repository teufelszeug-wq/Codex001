from uuid import UUID

from sqlalchemy.orm import Session

from app.domain import Project
from app.repositories import ChangeLogRepository, SqlAlchemyProjectRepository


class ProjectService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.projects = SqlAlchemyProjectRepository(session)
        self.change_log = ChangeLogRepository(session)

    def list_projects(self) -> list[Project]:
        return self.projects.list()

    def get_project(self, project_id: UUID) -> Project | None:
        return self.projects.get(project_id)

    def create_project(self, title: str) -> Project:
        cleaned = title.strip()
        if not cleaned:
            raise ValueError("Project title must not be empty")
        if len(cleaned) > 200:
            raise ValueError("Project title must be 200 characters or fewer")

        project = self.projects.create(cleaned)
        self.change_log.record_project_created(project.id, project.title)
        self.session.commit()
        return project
