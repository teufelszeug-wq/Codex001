from uuid import UUID

from sqlalchemy.orm import Session

from app.language_catalog import (
    DISPLAY_MODES,
    EARTH_TERM_MODES,
    LANGUAGE_ROLES,
    REPLACEMENT_MODES,
    WRITING_DIRECTIONS,
    get_language_culture_catalog,
)
from app.language_engine import generate_names
from app.language_repositories import LanguageCultureRepository
from app.repositories import ChangeLogRepository, SqlAlchemyProjectRepository


class LanguageCultureService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.projects = SqlAlchemyProjectRepository(session)
        self.configs = LanguageCultureRepository(session)
        self.change_log = ChangeLogRepository(session)

    @staticmethod
    def catalog() -> dict[str, object]:
        return get_language_culture_catalog()

    def get_config(self, project_id: UUID) -> dict[str, object] | None:
        if self.projects.get(project_id) is None:
            raise LookupError("Project not found")
        return self.configs.get(project_id)

    def save_config(
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
        if self.projects.get(project_id) is None:
            raise LookupError("Project not found")
        if status not in {"draft", "configured"}:
            raise ValueError("Unknown Language & Culture Builder status")

        languages = self._validate_languages(languages)
        language_ids = {str(item["id"]) for item in languages}
        cultures = self._validate_cultures(cultures, language_ids)
        contacts = self._validate_contacts(contacts, language_ids)
        root_lexicon = self._validate_lexicon(root_lexicon, language_ids)

        if common_language_id and common_language_id not in language_ids:
            raise ValueError("Common language must reference an existing language")

        display_mode = str(display_policy.get("mode", "translated"))
        allowed_display = {item["key"] for item in DISPLAY_MODES}
        if display_mode not in allowed_display:
            raise ValueError("Unknown reader display mode")
        normalized_display = {
            "mode": display_mode,
            "first_mention": str(display_policy.get("first_mention", "original_with_reading")),
            "later_mentions": str(display_policy.get("later_mentions", "translated")),
            "ruby_policy": str(display_policy.get("ruby_policy", "project_choice")),
            "notes": str(display_policy.get("notes", "")).strip()[:2000],
        }

        earth_mode = str(earth_term_policy.get("mode", "warn"))
        replacement_mode = str(earth_term_policy.get("replacement_mode", "both"))
        if earth_mode not in {item["key"] for item in EARTH_TERM_MODES}:
            raise ValueError("Unknown Earth-origin term mode")
        if replacement_mode not in {item["key"] for item in REPLACEMENT_MODES}:
            raise ValueError("Unknown Earth-origin replacement mode")
        normalized_earth = {
            "mode": earth_mode,
            "replacement_mode": replacement_mode,
            "allowed_contexts": self._string_list(earth_term_policy.get("allowed_contexts"), 30),
            "notes": str(earth_term_policy.get("notes", "")).strip()[:2000],
        }

        before = self.configs.get(project_id)
        saved = self.configs.upsert(
            project_id,
            languages=languages,
            cultures=cultures,
            contacts=contacts,
            root_lexicon=root_lexicon,
            display_policy=normalized_display,
            earth_term_policy=normalized_earth,
            common_language_id=common_language_id,
            status=status,
        )
        self.change_log.record(
            project_id=project_id,
            event_type="LANGUAGE_CULTURE_CONFIGURED" if before is None else "LANGUAGE_CULTURE_UPDATED",
            entity_type="LanguageCultureConfig",
            entity_id=project_id,
            before=before,
            after=saved,
            reason="M2.5 Language & Culture Builder",
        )
        self.session.commit()
        return saved

    def preview_names(self, project_id: UUID, language_id: str, *, kind: str, count: int, seed: int) -> list[str]:
        config = self.get_config(project_id)
        if config is None:
            raise LookupError("Language & Culture configuration not found")
        language = next((item for item in config["languages"] if str(item["id"]) == language_id), None)
        if language is None:
            raise LookupError("Language not found")
        if kind not in {"person", "place", "item", "title"}:
            raise ValueError("Unknown naming preview kind")
        return generate_names(language, kind=kind, count=max(1, min(30, count)), seed=seed)

    def _validate_languages(self, languages: list[dict[str, object]]) -> list[dict[str, object]]:
        allowed_roles = {item["key"] for item in LANGUAGE_ROLES}
        allowed_directions = {item["key"] for item in WRITING_DIRECTIONS}
        seen_ids: set[str] = set()
        normalized: list[dict[str, object]] = []

        for item in languages:
            identifier = str(item.get("id", "")).strip()
            name = str(item.get("name", "")).strip()
            if not identifier or identifier in seen_ids:
                raise ValueError("Every language needs a unique stable id")
            if not name or len(name) > 100:
                raise ValueError("Language name must be 1-100 characters")
            seen_ids.add(identifier)

            role = str(item.get("role", "regional"))
            if role not in allowed_roles:
                raise ValueError("Unknown language role")

            inspirations = item.get("inspirations") if isinstance(item.get("inspirations"), list) else []
            cleaned_inspirations = []
            for influence in inspirations[:20]:
                if not isinstance(influence, dict):
                    continue
                source = str(influence.get("source", "")).strip()
                weight = int(influence.get("weight", 50))
                if source and 0 <= weight <= 100:
                    cleaned_inspirations.append({"source": source[:120], "weight": weight})

            phonology = item.get("phonology") if isinstance(item.get("phonology"), dict) else {}
            normalized_phonology = {
                "onsets": self._string_list(phonology.get("onsets"), 100),
                "nuclei": self._string_list(phonology.get("nuclei"), 100),
                "codas": self._string_list(phonology.get("codas"), 100, allow_empty=True),
                "forbidden_sequences": self._string_list(phonology.get("forbidden_sequences"), 100),
                "syllables_min": max(1, min(6, int(phonology.get("syllables_min", 2)))),
                "syllables_max": max(1, min(8, int(phonology.get("syllables_max", 3)))),
                "separator": str(phonology.get("separator", ""))[:8],
                "capitalize": bool(phonology.get("capitalize", True)),
            }
            if normalized_phonology["syllables_max"] < normalized_phonology["syllables_min"]:
                normalized_phonology["syllables_max"] = normalized_phonology["syllables_min"]

            naming = item.get("naming") if isinstance(item.get("naming"), dict) else {}
            prefixes = naming.get("prefixes") if isinstance(naming.get("prefixes"), dict) else {}
            suffixes = naming.get("suffixes") if isinstance(naming.get("suffixes"), dict) else {}
            normalized_naming = {
                "prefixes": {kind: self._string_list(prefixes.get(kind), 50, allow_empty=True) for kind in ("person", "place", "item", "title")},
                "suffixes": {kind: self._string_list(suffixes.get(kind), 50, allow_empty=True) for kind in ("person", "place", "item", "title")},
                "notes": str(naming.get("notes", "")).strip()[:2000],
            }

            script = item.get("script") if isinstance(item.get("script"), dict) else {}
            direction = str(script.get("direction", "ltr"))
            if direction not in allowed_directions:
                raise ValueError("Unknown writing direction")
            normalized_script = {
                "name": str(script.get("name", "")).strip()[:100],
                "type": str(script.get("type", "alphabetic")).strip()[:80],
                "direction": direction,
                "notes": str(script.get("notes", "")).strip()[:2000],
            }

            raw_parent = item.get("parent_language_id")
            parent_language_id = None if raw_parent is None else str(raw_parent).strip() or None
            normalized.append(
                {
                    "id": identifier,
                    "name": name,
                    "role": role,
                    "regions": self._string_list(item.get("regions"), 50),
                    "inspirations": cleaned_inspirations,
                    "parent_language_id": parent_language_id,
                    "era_label": str(item.get("era_label", "")).strip()[:100],
                    "phonology": normalized_phonology,
                    "naming": normalized_naming,
                    "script": normalized_script,
                    "notes": str(item.get("notes", "")).strip()[:4000],
                }
            )

        valid_ids = {str(item["id"]) for item in normalized}
        for item in normalized:
            parent = item["parent_language_id"]
            if parent and parent not in valid_ids:
                raise ValueError("Parent language must reference an existing language")
            if parent == item["id"]:
                raise ValueError("Language cannot be its own parent")

        return normalized

    def _validate_cultures(self, cultures: list[dict[str, object]], language_ids: set[str]) -> list[dict[str, object]]:
        seen_ids: set[str] = set()
        normalized = []
        for item in cultures:
            identifier = str(item.get("id", "")).strip()
            name = str(item.get("name", "")).strip()
            if not identifier or identifier in seen_ids:
                raise ValueError("Every culture needs a unique stable id")
            if not name or len(name) > 100:
                raise ValueError("Culture name must be 1-100 characters")
            seen_ids.add(identifier)
            linked = self._string_list(item.get("language_ids"), 30)
            if set(linked) - language_ids:
                raise ValueError("Culture references an unknown language")
            normalized.append(
                {
                    "id": identifier,
                    "name": name,
                    "regions": self._string_list(item.get("regions"), 50),
                    "language_ids": linked,
                    "tags": self._string_list(item.get("tags"), 100),
                    "institutions": self._string_list(item.get("institutions"), 100),
                    "etiquette": str(item.get("etiquette", "")).strip()[:4000],
                    "taboos": self._string_list(item.get("taboos"), 100),
                    "festivals": self._string_list(item.get("festivals"), 100),
                    "material_culture": str(item.get("material_culture", "")).strip()[:4000],
                    "notes": str(item.get("notes", "")).strip()[:4000],
                }
            )
        return normalized

    def _validate_contacts(self, contacts: list[dict[str, object]], language_ids: set[str]) -> list[dict[str, object]]:
        normalized = []
        for item in contacts:
            source = str(item.get("from_language_id", "")).strip()
            target = str(item.get("to_language_id", "")).strip()
            if source not in language_ids or target not in language_ids or source == target:
                raise ValueError("Language contact must reference two different existing languages")
            intensity = int(item.get("intensity", 50))
            if not 0 <= intensity <= 100:
                raise ValueError("Language contact intensity must be between 0 and 100")
            normalized.append(
                {
                    "from_language_id": source,
                    "to_language_id": target,
                    "intensity": intensity,
                    "domains": self._string_list(item.get("domains"), 30),
                    "borrowing_policy": str(item.get("borrowing_policy", "adapt")).strip()[:80],
                    "notes": str(item.get("notes", "")).strip()[:2000],
                }
            )
        return normalized

    def _validate_lexicon(self, entries: list[dict[str, object]], language_ids: set[str]) -> list[dict[str, object]]:
        normalized = []
        seen_ids: set[str] = set()
        for item in entries:
            identifier = str(item.get("id", "")).strip()
            language_id = str(item.get("language_id", "")).strip()
            form = str(item.get("form", "")).strip()
            meaning = str(item.get("meaning", "")).strip()
            if not identifier or identifier in seen_ids:
                raise ValueError("Every root lexicon entry needs a unique stable id")
            if language_id not in language_ids:
                raise ValueError("Root lexicon entry references an unknown language")
            if not form or not meaning:
                raise ValueError("Root lexicon entry requires form and meaning")
            seen_ids.add(identifier)
            normalized.append(
                {
                    "id": identifier,
                    "language_id": language_id,
                    "form": form[:120],
                    "meaning": meaning[:240],
                    "tags": self._string_list(item.get("tags"), 50),
                    "origin": str(item.get("origin", "native")).strip()[:80],
                    "notes": str(item.get("notes", "")).strip()[:2000],
                }
            )
        return normalized

    @staticmethod
    def _string_list(value: object, limit: int, allow_empty: bool = False) -> list[str]:
        if not isinstance(value, list):
            return []
        result = []
        for raw in value[:limit]:
            text = str(raw).strip()
            if text or allow_empty:
                result.append(text[:120])
        return result
