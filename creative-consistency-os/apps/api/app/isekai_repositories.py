from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.isekai_catalog import default_isekai_config
from app.models import IsekaiPackConfigModel, utcnow


class IsekaiPackRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, project_id: UUID) -> dict[str, object] | None:
        row = self.session.get(IsekaiPackConfigModel, str(project_id))
        if row is None:
            return None
        return {
            "project_id": row.project_id,
            "enabled": row.enabled,
            "strictness": row.strictness,
            "enabled_categories": json.loads(row.enabled_categories_json),
            "allow_terms": json.loads(row.allow_terms_json),
            "custom_terms": json.loads(row.custom_terms_json),
            "replacements": json.loads(row.replacements_json),
            "require_world_mapping": row.require_world_mapping,
            "travel_routes": json.loads(row.travel_routes_json),
            "magic_policy": json.loads(row.magic_policy_json),
            "economy_policy": json.loads(row.economy_policy_json),
            "healing_policy": json.loads(row.healing_policy_json),
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
            **default_isekai_config(),
            "pack_version": 1,
            "updated_at": None,
        }

    def upsert(self, project_id: UUID, config: dict[str, object]) -> dict[str, object]:
        row = self.session.get(IsekaiPackConfigModel, str(project_id))
        if row is None:
            row = IsekaiPackConfigModel(project_id=str(project_id))
            self.session.add(row)

        row.enabled = bool(config["enabled"])
        row.strictness = str(config["strictness"])
        row.enabled_categories_json = json.dumps(config["enabled_categories"], ensure_ascii=False)
        row.allow_terms_json = json.dumps(config["allow_terms"], ensure_ascii=False)
        row.custom_terms_json = json.dumps(config["custom_terms"], ensure_ascii=False)
        row.replacements_json = json.dumps(config["replacements"], ensure_ascii=False)
        row.require_world_mapping = bool(config["require_world_mapping"])
        row.travel_routes_json = json.dumps(config["travel_routes"], ensure_ascii=False)
        row.magic_policy_json = json.dumps(config["magic_policy"], ensure_ascii=False)
        row.economy_policy_json = json.dumps(config["economy_policy"], ensure_ascii=False)
        row.healing_policy_json = json.dumps(config["healing_policy"], ensure_ascii=False)
        row.status = str(config["status"])
        row.pack_version = 1
        row.updated_at = utcnow()
        self.session.flush()
        return self.get(project_id) or self.get_or_default(project_id)
