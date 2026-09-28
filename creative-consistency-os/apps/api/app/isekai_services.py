from __future__ import annotations

import unicodedata
from uuid import UUID

from sqlalchemy.orm import Session

from app.impact_repositories import ImpactRepository
from app.isekai_catalog import (
    EARTH_TERM_CATALOG,
    DEFAULT_ENABLED_CATEGORIES,
    ISEKAI_CATEGORIES,
    ISEKAI_STATUS,
    ISEKAI_STRICTNESS,
    default_isekai_config,
)
from app.isekai_repositories import IsekaiPackRepository
from app.repositories import ChangeLogRepository, SqlAlchemyProjectRepository
from app.writing_repositories import BibleRepository


def normalize_term(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().strip().split())


class IsekaiPackService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.projects = SqlAlchemyProjectRepository(session)
        self.bible = BibleRepository(session)
        self.repo = IsekaiPackRepository(session)
        self.change_log = ChangeLogRepository(session)
        self.impact = ImpactRepository(session)

    @staticmethod
    def catalog() -> dict[str, object]:
        return {
            "categories": [
                {"key": key, **value}
                for key, value in ISEKAI_CATEGORIES.items()
            ],
            "earth_terms": EARTH_TERM_CATALOG,
            "strictness": ISEKAI_STRICTNESS,
            "attribute_contracts": {
                "travel_event": {
                    "entity_type": "event",
                    "attributes.isekai_travel": {
                        "from_entity_id": "Bible place/entity UUID",
                        "to_entity_id": "Bible place/entity UUID",
                        "mode": "route mode",
                        "duration_hours": "number",
                    },
                },
                "spell_magic": {
                    "entity_type": "spell",
                    "attributes.magic.cost": {"type": "string", "value": "number"},
                    "attributes.magic.tier": "optional string",
                },
                "item_economy": {
                    "entity_type": "item",
                    "attributes.economy": {
                        "category": "string",
                        "currency": "string",
                        "price": "number",
                    },
                },
                "spell_healing": {
                    "entity_type": "spell",
                    "attributes.healing": {
                        "resurrection": "boolean",
                        "limb_regrowth": "boolean",
                    },
                },
            },
            "pack_version": 1,
        }

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
            event_type="ISEKAI_PACK_CONFIG_UPDATED",
            entity_type="IsekaiPackConfig",
            entity_id=project_id,
            before=before,
            after=saved,
            reason="M5 isekai pack configuration",
        )
        self.impact.queue_invalidation(
            project_id,
            source_type="IsekaiPackConfig",
            source_id=str(project_id),
            change_kind="ISEKAI_PACK_CONFIG_UPDATED",
            detail={"before": before, "after": saved},
        )
        self.session.commit()
        return saved

    def replacement_preview(self, project_id: UUID, term: str) -> dict[str, object]:
        config = self.get(project_id)
        surface = term.strip()
        if not surface:
            raise ValueError("Term must not be empty")
        normalized = normalize_term(surface)
        entries = self._term_entries(config)
        match = next((item for item in entries if normalize_term(str(item["term"])) == normalized), None)
        if match is None:
            return {
                "term": surface,
                "matched": False,
                "allowed": False,
                "category": None,
                "concept_key": None,
                "generic_replacement": None,
                "world_replacement": None,
                "source_place_entity_id": None,
                "needs_author_decision": True,
            }
        allow_terms = {normalize_term(str(item)) for item in config.get("allow_terms", [])}
        replacements = {
            normalize_term(str(item.get("earth_term", ""))): item
            for item in config.get("replacements", [])
            if isinstance(item, dict)
        }
        replacement = replacements.get(normalized)
        return {
            "term": surface,
            "matched": True,
            "allowed": normalized in allow_terms,
            "category": match.get("category"),
            "concept_key": match.get("concept_key"),
            "generic_replacement": match.get("generic_replacement"),
            "world_replacement": replacement.get("world_term") if replacement else None,
            "source_place_entity_id": replacement.get("source_place_entity_id") if replacement else None,
            "notes": replacement.get("notes", "") if replacement else "",
            "needs_author_decision": replacement is None,
        }

    def _validate(self, project_id: UUID, payload: dict[str, object]) -> dict[str, object]:
        base = default_isekai_config()
        merged = {**base, **payload}

        strictness = str(merged.get("strictness", "standard"))
        if strictness not in ISEKAI_STRICTNESS:
            raise ValueError("Unknown isekai strictness")
        status = str(merged.get("status", "draft"))
        if status not in ISEKAI_STATUS:
            raise ValueError("Unknown isekai pack status")

        categories = merged.get("enabled_categories", {})
        if not isinstance(categories, dict):
            raise ValueError("enabled_categories must be an object")
        unknown_categories = set(categories) - set(ISEKAI_CATEGORIES)
        if unknown_categories:
            raise ValueError("Unknown isekai category")
        cleaned_categories = {
            key: bool(categories.get(key, DEFAULT_ENABLED_CATEGORIES[key]))
            for key in ISEKAI_CATEGORIES
        }

        allow_terms = merged.get("allow_terms", [])
        if not isinstance(allow_terms, list):
            raise ValueError("allow_terms must be a list")
        cleaned_allow_terms = []
        seen_allow = set()
        for value in allow_terms:
            term = str(value).strip()
            if not term or len(term) > 200:
                raise ValueError("Allow term must be 1-200 characters")
            normalized = normalize_term(term)
            if normalized not in seen_allow:
                seen_allow.add(normalized)
                cleaned_allow_terms.append(term)

        custom_terms = merged.get("custom_terms", [])
        if not isinstance(custom_terms, list):
            raise ValueError("custom_terms must be a list")
        cleaned_custom: list[dict[str, object]] = []
        for index, item in enumerate(custom_terms):
            if not isinstance(item, dict):
                raise ValueError("Custom earth term must be an object")
            term = str(item.get("term", "")).strip()
            category = str(item.get("category", "earth_culture_food"))
            if not term or len(term) > 200:
                raise ValueError("Custom earth term must be 1-200 characters")
            if category not in ISEKAI_CATEGORIES:
                raise ValueError("Unknown custom earth-term category")
            severity = item.get("severity")
            if severity is not None and str(severity) not in {"hint", "info", "warning", "error"}:
                raise ValueError("Unknown custom earth-term severity")
            cleaned_custom.append({
                "id": str(item.get("id") or f"earth-term-{index + 1}")[:100],
                "term": term,
                "category": category,
                "concept_key": str(item.get("concept_key", "custom"))[:120],
                "generic_replacement": str(item.get("generic_replacement", ""))[:200],
                "severity": str(severity) if severity is not None else None,
                "enabled": bool(item.get("enabled", True)),
            })

        replacements = merged.get("replacements", [])
        if not isinstance(replacements, list):
            raise ValueError("replacements must be a list")
        cleaned_replacements: list[dict[str, object]] = []
        for item in replacements:
            if not isinstance(item, dict):
                raise ValueError("Replacement must be an object")
            earth_term = str(item.get("earth_term", "")).strip()
            world_term = str(item.get("world_term", "")).strip()
            if not earth_term or not world_term:
                raise ValueError("Replacement requires earth_term and world_term")
            source_id = item.get("source_place_entity_id")
            if source_id:
                try:
                    source_uuid = UUID(str(source_id))
                except ValueError as exc:
                    raise ValueError("source_place_entity_id must be UUID") from exc
                if self.bible.get(project_id, source_uuid) is None:
                    raise ValueError("Replacement source place must reference an existing Bible entity")
                source_id = str(source_uuid)
            cleaned_replacements.append({
                "earth_term": earth_term[:200],
                "world_term": world_term[:200],
                "source_place_entity_id": source_id,
                "notes": str(item.get("notes", ""))[:2000],
            })

        travel_routes = merged.get("travel_routes", [])
        if not isinstance(travel_routes, list):
            raise ValueError("travel_routes must be a list")
        cleaned_routes: list[dict[str, object]] = []
        for index, item in enumerate(travel_routes):
            if not isinstance(item, dict):
                raise ValueError("Travel route must be an object")
            try:
                from_id = UUID(str(item.get("from_entity_id")))
                to_id = UUID(str(item.get("to_entity_id")))
            except ValueError as exc:
                raise ValueError("Travel route endpoints must be UUIDs") from exc
            if from_id == to_id:
                raise ValueError("Travel route endpoints must differ")
            if self.bible.get(project_id, from_id) is None or self.bible.get(project_id, to_id) is None:
                raise ValueError("Travel route endpoints must reference Bible entities")
            min_hours = float(item.get("min_hours", 0))
            max_hours = float(item.get("max_hours", 0))
            if min_hours < 0 or max_hours <= 0 or min_hours > max_hours:
                raise ValueError("Travel route hours are invalid")
            mode = str(item.get("mode", "")).strip()
            if not mode:
                raise ValueError("Travel route mode is required")
            cleaned_routes.append({
                "id": str(item.get("id") or f"route-{index + 1}")[:100],
                "from_entity_id": str(from_id),
                "to_entity_id": str(to_id),
                "mode": mode[:100],
                "min_hours": min_hours,
                "max_hours": max_hours,
                "bidirectional": bool(item.get("bidirectional", True)),
                "notes": str(item.get("notes", ""))[:2000],
            })

        magic = merged.get("magic_policy", {})
        if not isinstance(magic, dict):
            raise ValueError("magic_policy must be an object")
        allowed_cost_types = magic.get("allowed_cost_types", [])
        costless_tiers = magic.get("costless_tiers", [])
        if not isinstance(allowed_cost_types, list) or not isinstance(costless_tiers, list):
            raise ValueError("Magic cost lists must be arrays")
        cleaned_magic = {
            "enabled": bool(magic.get("enabled", False)),
            "require_cost": bool(magic.get("require_cost", True)),
            "allowed_cost_types": [str(item).strip()[:100] for item in allowed_cost_types if str(item).strip()],
            "costless_tiers": [str(item).strip()[:100] for item in costless_tiers if str(item).strip()],
        }

        economy = merged.get("economy_policy", {})
        if not isinstance(economy, dict):
            raise ValueError("economy_policy must be an object")
        currencies = economy.get("currencies", [])
        price_bands = economy.get("price_bands", [])
        if not isinstance(currencies, list) or not isinstance(price_bands, list):
            raise ValueError("Economy lists must be arrays")
        cleaned_bands: list[dict[str, object]] = []
        for index, item in enumerate(price_bands):
            if not isinstance(item, dict):
                raise ValueError("Price band must be an object")
            minimum = float(item.get("min_price", 0))
            maximum = float(item.get("max_price", 0))
            if minimum < 0 or maximum < minimum:
                raise ValueError("Price band range is invalid")
            category = str(item.get("category", "")).strip()
            currency = str(item.get("currency", "")).strip()
            if not category or not currency:
                raise ValueError("Price band category and currency are required")
            cleaned_bands.append({
                "id": str(item.get("id") or f"price-band-{index + 1}")[:100],
                "category": category[:100],
                "currency": currency[:100],
                "min_price": minimum,
                "max_price": maximum,
                "notes": str(item.get("notes", ""))[:2000],
            })
        cleaned_economy = {
            "enabled": bool(economy.get("enabled", False)),
            "currencies": [str(item).strip()[:100] for item in currencies if str(item).strip()],
            "price_bands": cleaned_bands,
        }

        healing = merged.get("healing_policy", {})
        if not isinstance(healing, dict):
            raise ValueError("healing_policy must be an object")
        cleaned_healing = {
            "enabled": bool(healing.get("enabled", False)),
            "resurrection_allowed": bool(healing.get("resurrection_allowed", False)),
            "limb_regrowth_allowed": bool(healing.get("limb_regrowth_allowed", False)),
        }

        return {
            "enabled": bool(merged.get("enabled", False)),
            "strictness": strictness,
            "enabled_categories": cleaned_categories,
            "allow_terms": cleaned_allow_terms,
            "custom_terms": cleaned_custom,
            "replacements": cleaned_replacements,
            "require_world_mapping": bool(merged.get("require_world_mapping", False)),
            "travel_routes": cleaned_routes,
            "magic_policy": cleaned_magic,
            "economy_policy": cleaned_economy,
            "healing_policy": cleaned_healing,
            "status": status,
        }

    @staticmethod
    def _term_entries(config: dict[str, object]) -> list[dict[str, object]]:
        entries: list[dict[str, object]] = [dict(item) for item in EARTH_TERM_CATALOG]
        for item in config.get("custom_terms", []):
            if isinstance(item, dict) and item.get("enabled", True):
                entries.append(dict(item))
        return entries
