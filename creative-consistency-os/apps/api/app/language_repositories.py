import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import LanguageCultureConfigModel, utcnow


class LanguageCultureRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, project_id: UUID) -> dict[str, object] | None:
        row = self.session.get(LanguageCultureConfigModel, str(project_id))
        return self._to_dict(row) if row else None

    def upsert(
        self,
        project_id: UUID,
        *,
        languages: list[dict[str, object]],
        cultures: list[dict[str, object]],
        contacts: list[dict[str, object]],
        root_lexicon: list[dict[str, object]],
        display_policy: dict[str, object],
        earth_term_policy: dict[str, object],
        common_language_id: str | None,
        status: str,
    ) -> dict[str, object]:
        row = self.session.get(LanguageCultureConfigModel, str(project_id))
        if row is None:
            row = LanguageCultureConfigModel(project_id=str(project_id))
            self.session.add(row)

        row.languages_json = json.dumps(languages, ensure_ascii=False)
        row.cultures_json = json.dumps(cultures, ensure_ascii=False)
        row.contacts_json = json.dumps(contacts, ensure_ascii=False)
        row.root_lexicon_json = json.dumps(root_lexicon, ensure_ascii=False)
        row.display_policy_json = json.dumps(display_policy, ensure_ascii=False)
        row.earth_term_policy_json = json.dumps(earth_term_policy, ensure_ascii=False)
        row.common_language_id = common_language_id
        row.status = status
        row.builder_version = 1
        row.updated_at = utcnow()
        self.session.flush()
        return self._to_dict(row)

    @staticmethod
    def _to_dict(row: LanguageCultureConfigModel) -> dict[str, object]:
        return {
            "project_id": row.project_id,
            "languages": json.loads(row.languages_json),
            "cultures": json.loads(row.cultures_json),
            "contacts": json.loads(row.contacts_json),
            "root_lexicon": json.loads(row.root_lexicon_json),
            "display_policy": json.loads(row.display_policy_json),
            "earth_term_policy": json.loads(row.earth_term_policy_json),
            "common_language_id": row.common_language_id,
            "status": row.status,
            "builder_version": row.builder_version,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
