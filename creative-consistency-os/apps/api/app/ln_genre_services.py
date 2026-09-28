from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.impact_repositories import ImpactRepository
from app.ln_genre_catalog import (
    DEFAULT_NOBLE_POLICY,
    DEFAULT_PALACE_POLICY,
    DEFAULT_ROMCOM_POLICY,
    LN_STATUS,
    PACK_KEYS,
    catalog_payload,
    default_ln_genre_config,
)
from app.ln_genre_repositories import LNGenrePackRepository
from app.repositories import ChangeLogRepository, SqlAlchemyProjectRepository
from app.writing_repositories import BibleRepository


SEVERITIES = {"hint", "info", "warning", "error"}


class LNGenrePackService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.projects = SqlAlchemyProjectRepository(session)
        self.bible = BibleRepository(session)
        self.repo = LNGenrePackRepository(session)
        self.impact = ImpactRepository(session)
        self.change_log = ChangeLogRepository(session)

    @staticmethod
    def catalog() -> dict[str, object]:
        return catalog_payload()

    def _project_exists(self, project_id: UUID) -> None:
        if self.projects.get(project_id) is None:
            raise LookupError("Project not found")

    def get(self, project_id: UUID) -> dict[str, object]:
        self._project_exists(project_id)
        return self.repo.get_or_default(project_id)

    def save(self, project_id: UUID, payload: dict[str, object]) -> dict[str, object]:
        self._project_exists(project_id)
        before = self.repo.get(project_id)
        cleaned = self._validate(project_id, payload)
        saved = self.repo.upsert(project_id, cleaned)
        self.change_log.record(
            project_id=project_id,
            event_type="LN_GENRE_PACK_CONFIG_UPDATED",
            entity_type="LNGenrePackConfig",
            entity_id=project_id,
            before=before,
            after=saved,
            reason="M6 LN genre pack configuration",
        )
        self.impact.queue_invalidation(
            project_id,
            source_type="LNGenrePackConfig",
            source_id=str(project_id),
            change_kind="LN_GENRE_PACK_CONFIG_UPDATED",
            detail={"before": before, "after": saved},
        )
        self.session.commit()
        return saved

    def _validate(self, project_id: UUID, payload: dict[str, object]) -> dict[str, object]:
        base = default_ln_genre_config()
        merged = {**base, **payload}
        status = str(merged.get("status", "draft"))
        if status not in LN_STATUS:
            raise ValueError("Unknown LN genre pack status")

        enabled = merged.get("enabled_packs", {})
        if not isinstance(enabled, dict):
            raise ValueError("enabled_packs must be an object")
        unknown = set(enabled) - set(PACK_KEYS)
        if unknown:
            raise ValueError("Unknown LN genre pack")
        cleaned_enabled = {key: bool(enabled.get(key, False)) for key in PACK_KEYS}

        noble = self._validate_noble(project_id, merged.get("noble_lady", {}))
        palace = self._validate_palace(project_id, merged.get("palace_harem", {}))
        romcom = self._validate_romcom(merged.get("romcom", {}))
        return {
            "enabled_packs": cleaned_enabled,
            "noble_lady": noble,
            "palace_harem": palace,
            "romcom": romcom,
            "status": status,
        }

    def _validate_noble(self, project_id: UUID, value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            raise ValueError("noble_lady must be an object")
        merged = {**DEFAULT_NOBLE_POLICY, **value}
        ranks = self._string_list(merged.get("rank_order"), "noble rank_order")
        if len(set(ranks)) != len(ranks):
            raise ValueError("noble rank_order contains duplicates")

        title_map = merged.get("rank_title_map", {})
        if not isinstance(title_map, dict):
            raise ValueError("rank_title_map must be an object")
        cleaned_titles: dict[str, list[str]] = {}
        for rank, titles in title_map.items():
            if rank not in ranks:
                raise ValueError("rank_title_map contains unknown rank")
            cleaned_titles[str(rank)] = self._string_list(titles, "rank titles")

        address_rules = merged.get("address_rules", [])
        if not isinstance(address_rules, list):
            raise ValueError("address_rules must be a list")
        cleaned_addresses: list[dict[str, object]] = []
        for index, item in enumerate(address_rules):
            if not isinstance(item, dict):
                raise ValueError("address rule must be an object")
            target_rank = str(item.get("target_rank", "")).strip()
            if target_rank not in ranks:
                raise ValueError("address rule target_rank is unknown")
            allowed = self._string_list(item.get("allowed_addresses", []), "allowed addresses")
            cleaned_addresses.append({
                "id": str(item.get("id") or f"address-{index + 1}")[:100],
                "target_rank": target_rank,
                "allowed_addresses": allowed,
            })

        relation_types = self._string_list(
            merged.get("engagement_relation_types", ["engaged_to", "betrothed_to"]),
            "engagement relation types",
        )
        return {
            "rank_order": ranks,
            "rank_title_map": cleaned_titles,
            "address_rules": cleaned_addresses,
            "allow_multiple_active_engagements": bool(merged.get("allow_multiple_active_engagements", False)),
            "engagement_relation_types": relation_types,
        }

    def _validate_palace(self, project_id: UUID, value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            raise ValueError("palace_harem must be an object")
        merged = {**DEFAULT_PALACE_POLICY, **value}
        ranks = self._string_list(merged.get("rank_order"), "palace rank_order")
        if len(set(ranks)) != len(ranks):
            raise ValueError("palace rank_order contains duplicates")

        restricted = merged.get("restricted_areas", [])
        if not isinstance(restricted, list):
            raise ValueError("restricted_areas must be a list")
        cleaned_areas: list[dict[str, object]] = []
        for index, item in enumerate(restricted):
            if not isinstance(item, dict):
                raise ValueError("restricted area must be an object")
            place_id = self._existing_uuid(project_id, item.get("place_entity_id"), "restricted area place")
            min_rank = str(item.get("min_rank", "")).strip()
            if min_rank and min_rank not in ranks:
                raise ValueError("restricted area min_rank is unknown")
            allowed_factions = self._existing_uuid_list(
                project_id,
                item.get("allowed_faction_entity_ids", []),
                "restricted area factions",
            )
            exceptions = self._existing_uuid_list(
                project_id,
                item.get("exception_entity_ids", []),
                "restricted area exceptions",
            )
            cleaned_areas.append({
                "id": str(item.get("id") or f"area-{index + 1}")[:100],
                "place_entity_id": place_id,
                "min_rank": min_rank,
                "allowed_faction_entity_ids": allowed_factions,
                "exception_entity_ids": exceptions,
            })

        information = merged.get("information_rules", [])
        if not isinstance(information, list):
            raise ValueError("information_rules must be a list")
        cleaned_info: list[dict[str, object]] = []
        for index, item in enumerate(information):
            if not isinstance(item, dict):
                raise ValueError("information rule must be an object")
            fact_key = str(item.get("fact_key", "")).strip()
            if not fact_key:
                raise ValueError("information rule fact_key is required")
            min_rank = str(item.get("min_rank", "")).strip()
            if min_rank and min_rank not in ranks:
                raise ValueError("information rule min_rank is unknown")
            allowed_factions = self._existing_uuid_list(
                project_id,
                item.get("allowed_faction_entity_ids", []),
                "information factions",
            )
            cleaned_info.append({
                "id": str(item.get("id") or f"info-{index + 1}")[:100],
                "fact_key": fact_key[:120],
                "min_rank": min_rank,
                "allowed_faction_entity_ids": allowed_factions,
            })

        rituals = merged.get("ritual_sequences", [])
        if not isinstance(rituals, list):
            raise ValueError("ritual_sequences must be a list")
        cleaned_rituals: list[dict[str, object]] = []
        for index, item in enumerate(rituals):
            if not isinstance(item, dict):
                raise ValueError("ritual sequence must be an object")
            key = str(item.get("ritual_key", "")).strip()
            if not key:
                raise ValueError("ritual_key is required")
            steps = self._string_list(item.get("steps", []), "ritual steps")
            if len(set(steps)) != len(steps):
                raise ValueError("ritual steps contain duplicates")
            cleaned_rituals.append({
                "id": str(item.get("id") or f"ritual-{index + 1}")[:100],
                "ritual_key": key[:120],
                "steps": steps,
            })

        return {
            "rank_order": ranks,
            "restricted_areas": cleaned_areas,
            "information_rules": cleaned_info,
            "ritual_sequences": cleaned_rituals,
        }

    def _validate_romcom(self, value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            raise ValueError("romcom must be an object")
        merged = {**DEFAULT_ROMCOM_POLICY, **value}
        stages = self._string_list(merged.get("stages"), "romcom stages")
        if len(stages) < 2 or len(set(stages)) != len(stages):
            raise ValueError("romcom stages must contain at least two unique values")
        max_jump = int(merged.get("max_stage_jump", 1))
        if max_jump < 1 or max_jump > len(stages):
            raise ValueError("max_stage_jump is invalid")
        severity = str(merged.get("unresolved_misunderstanding_severity", "info"))
        if severity not in SEVERITIES:
            raise ValueError("Unknown unresolved misunderstanding severity")
        return {
            "stages": stages,
            "max_stage_jump": max_jump,
            "allow_regression": bool(merged.get("allow_regression", True)),
            "require_reason_for_large_jump": bool(merged.get("require_reason_for_large_jump", True)),
            "unresolved_misunderstanding_severity": severity,
        }

    @staticmethod
    def _string_list(value: object, label: str) -> list[str]:
        if not isinstance(value, list):
            raise ValueError(f"{label} must be a list")
        result = [str(item).strip()[:120] for item in value if str(item).strip()]
        if not result:
            raise ValueError(f"{label} must not be empty")
        return result

    def _existing_uuid(self, project_id: UUID, value: object, label: str) -> str:
        try:
            entity_id = UUID(str(value))
        except ValueError as exc:
            raise ValueError(f"{label} must be UUID") from exc
        if self.bible.get(project_id, entity_id) is None:
            raise ValueError(f"{label} must reference an existing Bible entity")
        return str(entity_id)

    def _existing_uuid_list(self, project_id: UUID, value: object, label: str) -> list[str]:
        if not isinstance(value, list):
            raise ValueError(f"{label} must be a list")
        result: list[str] = []
        for item in value:
            result.append(self._existing_uuid(project_id, item, label))
        return result
