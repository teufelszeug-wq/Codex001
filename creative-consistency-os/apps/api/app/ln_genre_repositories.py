from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.ln_genre_catalog import default_ln_genre_config
from app.models import LNGenrePackConfigModel, utcnow


class LNGenrePackRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, project_id: UUID) -> dict[str, object] | None:
        row = self.session.get(LNGenrePackConfigModel, str(project_id))
        if row is None:
            return None
        return {
            "project_id": row.project_id,
            "enabled_packs": json.loads(row.enabled_packs_json),
            "noble_lady": json.loads(row.noble_lady_json),
            "palace_harem": json.loads(row.palace_harem_json),
            "romcom": json.loads(row.romcom_json),
            "status": row.status,
            "pack_version": row.pack_version,
            "updated_at": row.updated_at,
        }

    def get_or_default(self, project_id: UUID) -> dict[str, object]:
        stored = self.get(project_id)
        if stored is not None:
            return stored
        return {
            "project_id": str(project_id),
            **default_ln_genre_config(),
            "pack_version": 1,
            "updated_at": None,
        }

    def upsert(self, project_id: UUID, config: dict[str, object]) -> dict[str, object]:
        row = self.session.get(LNGenrePackConfigModel, str(project_id))
        if row is None:
            row = LNGenrePackConfigModel(project_id=str(project_id))
            self.session.add(row)

        row.enabled_packs_json = json.dumps(config["enabled_packs"], ensure_ascii=False)
        row.noble_lady_json = json.dumps(config["noble_lady"], ensure_ascii=False)
        row.palace_harem_json = json.dumps(config["palace_harem"], ensure_ascii=False)
        row.romcom_json = json.dumps(config["romcom"], ensure_ascii=False)
        row.status = str(config["status"])
        row.pack_version = 1
        row.updated_at = utcnow()
        self.session.flush()
        return self.get(project_id) or self.get_or_default(project_id)
