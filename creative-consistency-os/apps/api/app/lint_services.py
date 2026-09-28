from __future__ import annotations

import difflib
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain import CanonState
from app.entity_repositories import EntityIntelligenceRepository
from app.isekai_catalog import EARTH_TERM_CATALOG, STRICTNESS_TO_SEVERITY
from app.isekai_repositories import IsekaiPackRepository
from app.lint_repositories import LintRepository
from app.ln_genre_repositories import LNGenrePackRepository
from app.repositories import ChangeLogRepository, SqlAlchemyProjectRepository
from app.writing_repositories import BibleRepository, ManuscriptRepository, TimelineRepository


SEVERITIES = {"hint", "info", "warning", "error"}
FINDING_STATES = {"OPEN", "ACKNOWLEDGED", "IGNORED", "RESOLVED"}

BUILTIN_RULES: dict[str, dict[str, object]] = {
    "mention_index_missing": {
        "category": "entity",
        "default_severity": "info",
        "description": "本文があるのにEntity Mention indexがまだ作られていない。",
    },
    "mention_freshness": {
        "category": "entity",
        "default_severity": "warning",
        "description": "Entity Mentionが現在の本文Revisionより古い。",
    },
    "mention_span_mismatch": {
        "category": "integrity",
        "default_severity": "error",
        "description": "現在RevisionのMention spanと本文文字列が一致しない。",
    },
    "unresolved_mention": {
        "category": "entity",
        "default_severity": "warning",
        "description": "現在Revisionに未解決の固有表現候補がある。",
    },
    "ambiguous_mention": {
        "category": "entity",
        "default_severity": "warning",
        "description": "本文中の呼称が複数エンティティに一致する。",
    },
    "reference_inference": {
        "category": "canon",
        "default_severity": "info",
        "description": "本文がINFERENCE状態の設定を参照している。",
    },
    "reference_disputed": {
        "category": "canon",
        "default_severity": "error",
        "description": "本文がDISPUTED状態の設定を参照している。",
    },
    "reference_deprecated": {
        "category": "canon",
        "default_severity": "warning",
        "description": "本文がDEPRECATED状態の設定を参照している。",
    },
    "reference_inactive": {
        "category": "canon",
        "default_severity": "error",
        "description": "本文がARCHIVED/REJECTED状態の設定を参照している。",
    },
    "canonical_name_collision": {
        "category": "naming",
        "default_severity": "warning",
        "description": "同一正規化名を持つBibleエンティティが複数ある。",
    },
    "alias_collision": {
        "category": "naming",
        "default_severity": "warning",
        "description": "同じ別名が複数エンティティへ割り当てられている。",
    },
    "canon_timeline_noncanon_participant": {
        "category": "timeline",
        "default_severity": "warning",
        "description": "CANON時系列イベントが非CANON参加者を参照している。",
    },
    "canon_relation_noncanon_endpoint": {
        "category": "relation",
        "default_severity": "warning",
        "description": "CANON関係の端点が非CANONエンティティになっている。",
    },
    "possible_name_drift": {
        "category": "semantic",
        "default_severity": "hint",
        "description": "未解決呼称が既知の正式名・別名の表記揺れ候補かを字面類似度から提示する。",
    },
    "isekai_earth_origin_term": {
        "category": "isekai_immersion",
        "default_severity": "warning",
        "description": "異世界本文に地球固有の地名・文化・技術・制度等を強く想起させる語がある。",
        "pack": "isekai",
    },
    "isekai_world_term_unmapped": {
        "category": "isekai_immersion",
        "default_severity": "info",
        "description": "世界内置換を必須にした語へ、承認済みの世界内名称がまだ割り当てられていない。",
        "pack": "isekai",
    },
    "isekai_travel_duration": {
        "category": "isekai_travel",
        "default_severity": "error",
        "description": "構造化された移動イベントの所要時間が設定済みルート範囲から外れている。",
        "pack": "isekai",
    },
    "isekai_travel_route_unknown": {
        "category": "isekai_travel",
        "default_severity": "info",
        "description": "構造化された移動イベントに対応する移動ルート規則が見つからない。",
        "pack": "isekai",
    },
    "isekai_magic_cost_missing": {
        "category": "isekai_magic",
        "default_severity": "warning",
        "description": "コスト必須の魔法体系で、呪文のコスト情報が不足している。",
        "pack": "isekai",
    },
    "isekai_magic_cost_type": {
        "category": "isekai_magic",
        "default_severity": "warning",
        "description": "呪文が魔法体系で許可していないコスト種別を使用している。",
        "pack": "isekai",
    },
    "isekai_currency_unregistered": {
        "category": "isekai_economy",
        "default_severity": "warning",
        "description": "アイテム価格に世界設定へ登録されていない通貨が使われている。",
        "pack": "isekai",
    },
    "isekai_price_out_of_band": {
        "category": "isekai_economy",
        "default_severity": "warning",
        "description": "アイテム価格が設定済みカテゴリ価格帯から外れている。",
        "pack": "isekai",
    },
    "isekai_healing_limit": {
        "category": "isekai_magic",
        "default_severity": "error",
        "description": "治癒魔法の能力が世界設定上の回復限界を超えている。",
        "pack": "isekai",
    },
    "noble_rank_unknown": {
        "category": "noble_status",
        "default_severity": "warning",
        "description": "貴族キャラクターの爵位キーが作品の序列に存在しない。",
        "pack": "noble_lady",
    },
    "noble_house_reference_invalid": {
        "category": "noble_house",
        "default_severity": "error",
        "description": "キャラクターの所属家参照がStory Bibleに存在しない。",
        "pack": "noble_lady",
    },
    "noble_title_rank_mismatch": {
        "category": "noble_etiquette",
        "default_severity": "warning",
        "description": "公開称号が設定済み爵位の許可称号と一致しない。",
        "pack": "noble_lady",
    },
    "noble_multiple_active_engagements": {
        "category": "noble_engagement",
        "default_severity": "error",
        "description": "複数婚約を許可していない作品で同一人物に複数の有効婚約がある。",
        "pack": "noble_lady",
    },
    "noble_address_mismatch": {
        "category": "noble_etiquette",
        "default_severity": "warning",
        "description": "構造化された呼称イベントが対象爵位の呼称規則に一致しない。",
        "pack": "noble_lady",
    },
    "palace_rank_unknown": {
        "category": "palace_rank",
        "default_severity": "warning",
        "description": "後宮・宮廷キャラクターの位階キーが作品の序列に存在しない。",
        "pack": "palace_harem",
    },
    "palace_faction_reference_invalid": {
        "category": "palace_faction",
        "default_severity": "error",
        "description": "宮廷キャラクターの派閥参照がStory Bibleに存在しない。",
        "pack": "palace_harem",
    },
    "palace_restricted_area_access": {
        "category": "palace_access",
        "default_severity": "error",
        "description": "構造化された宮廷行動が立入権限規則を満たしていない。",
        "pack": "palace_harem",
    },
    "palace_information_access": {
        "category": "palace_information",
        "default_severity": "warning",
        "description": "キャラクターが位階・派閥上アクセスできない情報を取得している。",
        "pack": "palace_harem",
    },
    "palace_ritual_step_unknown": {
        "category": "palace_ritual",
        "default_severity": "warning",
        "description": "儀礼イベントに定義されていない手順キーが使われている。",
        "pack": "palace_harem",
    },
    "palace_ritual_order": {
        "category": "palace_ritual",
        "default_severity": "warning",
        "description": "儀礼イベントの手順順序が設定済みシーケンスと一致しない。",
        "pack": "palace_harem",
    },
    "romcom_stage_unknown": {
        "category": "romcom_relationship",
        "default_severity": "warning",
        "description": "恋愛関係遷移に未定義の関係段階が使われている。",
        "pack": "romcom",
    },
    "romcom_stage_jump": {
        "category": "romcom_relationship",
        "default_severity": "warning",
        "description": "恋愛関係の進展が設定した最大段階ジャンプを超えている。",
        "pack": "romcom",
    },
    "romcom_stage_regression": {
        "category": "romcom_relationship",
        "default_severity": "warning",
        "description": "関係段階の後退を許可していない設定で段階が後退している。",
        "pack": "romcom",
    },
    "romcom_schedule_conflict": {
        "category": "romcom_schedule",
        "default_severity": "error",
        "description": "同一人物の構造化予定が同じ日・時間帯で重複している。",
        "pack": "romcom",
    },
    "romcom_schedule_invalid": {
        "category": "romcom_schedule",
        "default_severity": "warning",
        "description": "構造化予定の開始・終了時刻が不正。",
        "pack": "romcom",
    },
    "romcom_misunderstanding_order": {
        "category": "romcom_misunderstanding",
        "default_severity": "warning",
        "description": "誤解のOPEN/RESOLVEライフサイクル順序が不正。",
        "pack": "romcom",
    },
    "romcom_misunderstanding_unresolved": {
        "category": "romcom_misunderstanding",
        "default_severity": "info",
        "description": "OPENされた誤解が構造化イベント上まだ解消されていない。",
        "pack": "romcom",
    },
}


def normalize_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().strip().split())


def fingerprint(parts: list[object]) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class LintService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.projects = SqlAlchemyProjectRepository(session)
        self.bible = BibleRepository(session)
        self.manuscripts = ManuscriptRepository(session)
        self.timeline = TimelineRepository(session)
        self.entities = EntityIntelligenceRepository(session)
        self.lint = LintRepository(session)
        self.isekai = IsekaiPackRepository(session)
        self.ln_genres = LNGenrePackRepository(session)
        self.change_log = ChangeLogRepository(session)

    @staticmethod
    def catalog() -> dict[str, object]:
        return {
            "builtins": [
                {
                    "rule_id": rule_id,
                    "category": spec["category"],
                    "default_severity": spec["default_severity"],
                    "description": spec["description"],
                    "pack": spec.get("pack", "core"),
                }
                for rule_id, spec in BUILTIN_RULES.items()
            ],
            "severities": ["hint", "info", "warning", "error"],
            "finding_states": ["OPEN", "ACKNOWLEDGED", "IGNORED", "RESOLVED"],
            "config_version": 1,
        }

    def _project_exists(self, project_id: UUID) -> None:
        if self.projects.get(project_id) is None:
            raise LookupError("Project not found")

    def get_config(self, project_id: UUID) -> dict[str, object]:
        self._project_exists(project_id)
        stored = self.lint.get_config(project_id)
        return stored or {
            "project_id": str(project_id),
            "rules": {"builtins": {}, "custom_terms": []},
            "config_version": 1,
            "updated_at": None,
        }

    def save_config(self, project_id: UUID, rules: dict[str, object]) -> dict[str, object]:
        self._project_exists(project_id)
        cleaned = self._validate_config(rules)
        before = self.lint.get_config(project_id)
        saved = self.lint.upsert_config(project_id, cleaned)
        self.change_log.record(
            project_id=project_id,
            event_type="LINT_CONFIG_UPDATED",
            entity_type="LintConfig",
            entity_id=project_id,
            before=before,
            after=saved,
            reason="M4 lint policy update",
        )
        self.session.commit()
        return saved

    def run_document(self, project_id: UUID, document_id: UUID) -> dict[str, object]:
        self._project_exists(project_id)
        document = self.manuscripts.get(project_id, document_id)
        if document is None:
            raise LookupError("Manuscript document not found")
        config = self.get_config(project_id)["rules"]
        findings = self._document_findings(project_id, document, config)
        summary = self._summary(findings)
        run = self.lint.create_run(
            project_id,
            document_id=document_id,
            scope="document",
            document_revision=int(document["current_revision"]),
            findings=findings,
            summary=summary,
        )
        self.change_log.record(
            project_id=project_id,
            event_type="LINT_RUN_COMPLETED",
            entity_type="ManuscriptDocument",
            entity_id=document_id,
            before=None,
            after={"run_id": run["id"], "summary": summary},
            reason="M4 document lint",
        )
        self.session.commit()
        return run

    def run_project(self, project_id: UUID) -> dict[str, object]:
        self._project_exists(project_id)
        config = self.get_config(project_id)["rules"]
        findings: list[dict[str, object]] = []
        for document in self.manuscripts.list(project_id):
            full = self.manuscripts.get(project_id, UUID(str(document["id"])))
            if full is not None:
                findings.extend(self._document_findings(project_id, full, config))
        findings.extend(self._project_findings(project_id, config))
        summary = self._summary(findings)
        run = self.lint.create_run(
            project_id,
            document_id=None,
            scope="project",
            document_revision=None,
            findings=findings,
            summary=summary,
        )
        self.change_log.record(
            project_id=project_id,
            event_type="LINT_RUN_COMPLETED",
            entity_type="Project",
            entity_id=project_id,
            before=None,
            after={"run_id": run["id"], "summary": summary},
            reason="M4 project lint",
        )
        self.session.commit()
        return run

    def run_structure(self, project_id: UUID) -> dict[str, object]:
        self._project_exists(project_id)
        config = self.get_config(project_id)["rules"]
        findings = self._project_findings(project_id, config)
        summary = self._summary(findings)
        run = self.lint.create_run(
            project_id,
            document_id=None,
            scope="structure",
            document_revision=None,
            findings=findings,
            summary=summary,
        )
        self.change_log.record(
            project_id=project_id,
            event_type="LINT_STRUCTURE_RUN_COMPLETED",
            entity_type="Project",
            entity_id=project_id,
            before=None,
            after={"run_id": run["id"], "summary": summary},
            reason="M6 structural lint",
        )
        self.session.commit()
        return run

    def list_runs(self, project_id: UUID) -> list[dict[str, object]]:
        self._project_exists(project_id)
        return self.lint.list_runs(project_id)

    def get_run(self, project_id: UUID, run_id: UUID) -> dict[str, object]:
        self._project_exists(project_id)
        run = self.lint.get_run(project_id, run_id)
        if run is None:
            raise LookupError("Lint run not found")
        return run

    def set_finding_state(self, project_id: UUID, finding_id: UUID, state: str) -> dict[str, object]:
        self._project_exists(project_id)
        if state not in FINDING_STATES:
            raise ValueError("Unknown finding state")
        updated = self.lint.set_finding_state(project_id, finding_id, state)
        if updated is None:
            raise LookupError("Lint finding not found")
        self.change_log.record(
            project_id=project_id,
            event_type="LINT_FINDING_STATE_CHANGED",
            entity_type="LintFinding",
            entity_id=finding_id,
            before=None,
            after={"state": state},
            reason="Author lint triage",
        )
        self.session.commit()
        return updated

    def _document_findings(
        self,
        project_id: UUID,
        document: dict[str, object],
        config: dict[str, object],
    ) -> list[dict[str, object]]:
        document_id = str(document["id"])
        revision = int(document["current_revision"])
        content = str(document.get("content", ""))
        mentions = self.entities.list_mentions(project_id, UUID(document_id))
        current_mentions = [item for item in mentions if int(item["revision_no"]) == revision]
        findings: list[dict[str, object]] = []

        if content and not mentions:
            self._append(
                findings,
                config,
                rule_id="mention_index_missing",
                document_id=document_id,
                message="本文は存在しますがEntity Mention indexがありません。Entity Intelligenceで現在Revisionをスキャンしてください。",
                evidence={"document_revision": revision},
            )
        elif mentions and not current_mentions:
            scanned_revisions = sorted({int(item["revision_no"]) for item in mentions})
            self._append(
                findings,
                config,
                rule_id="mention_freshness",
                document_id=document_id,
                message=f"Entity Mentionは旧Revision {scanned_revisions[-1]} の解析結果です。現在はRevision {revision}です。",
                evidence={"document_revision": revision, "mention_revisions": scanned_revisions},
            )

        bible_by_id = {str(item["id"]): item for item in self.bible.list(project_id)}
        known_surfaces: list[tuple[str, str, str]] = []
        for entity in bible_by_id.values():
            known_surfaces.append((
                str(entity["canonical_name"]),
                normalize_key(str(entity["canonical_name"])),
                str(entity["id"]),
            ))
        for alias in self.entities.list_aliases(project_id):
            known_surfaces.append((
                str(alias["alias"]),
                normalize_key(str(alias["alias"])),
                str(alias["entity_id"]),
            ))

        for mention in current_mentions:
            state = str(mention["resolver_state"])
            mention_start = int(mention["start_offset"])
            mention_end = int(mention["end_offset"])
            surface = str(mention["mention_text"])
            current_slice = content[mention_start:mention_end] if 0 <= mention_start <= mention_end <= len(content) else None
            if current_slice != surface:
                self._append(
                    findings,
                    config,
                    rule_id="mention_span_mismatch",
                    document_id=document_id,
                    message=f"現在RevisionのMention spanが本文「{surface}」と一致しません。再スキャンが必要です。",
                    start_offset=mention_start,
                    end_offset=mention_end,
                    evidence={
                        "mention_id": mention["id"],
                        "stored_surface": surface,
                        "current_slice": current_slice,
                        "revision_no": revision,
                    },
                )

            common = {
                "document_id": document_id,
                "start_offset": int(mention["start_offset"]),
                "end_offset": int(mention["end_offset"]),
                "evidence": {
                    "mention_id": mention["id"],
                    "mention_text": mention["mention_text"],
                    "confidence": mention["confidence"],
                    "candidate_ids": mention["candidate_ids"],
                    "revision_no": revision,
                },
            }
            if state == "unresolved":
                self._append(
                    findings,
                    config,
                    rule_id="unresolved_mention",
                    message=f"未解決の固有表現候補「{mention['mention_text']}」があります。",
                    **common,
                )
                normalized_surface = normalize_key(surface)
                best: tuple[float, str, str] | None = None
                for known_surface, normalized_known, entity_id in known_surfaces:
                    if not normalized_surface or not normalized_known or normalized_surface == normalized_known:
                        continue
                    score = difflib.SequenceMatcher(None, normalized_surface, normalized_known).ratio()
                    if score >= 0.82 and (best is None or score > best[0]):
                        best = (score, known_surface, entity_id)
                if best is not None:
                    self._append(
                        findings,
                        config,
                        rule_id="possible_name_drift",
                        document_id=document_id,
                        entity_id=best[2],
                        message=f"「{surface}」は既知名「{best[1]}」の表記揺れ候補です。",
                        start_offset=mention_start,
                        end_offset=mention_end,
                        evidence={
                            "mention_id": mention["id"],
                            "candidate_entity_id": best[2],
                            "candidate_surface": best[1],
                            "similarity": round(best[0], 4),
                            "provider": "deterministic_lexical_similarity_v1",
                        },
                    )
            elif state == "ambiguous":
                self._append(
                    findings,
                    config,
                    rule_id="ambiguous_mention",
                    message=f"「{mention['mention_text']}」は複数のエンティティ候補に一致します。",
                    **common,
                )
            elif state == "resolved" and mention.get("entity_id"):
                entity = bible_by_id.get(str(mention["entity_id"]))
                if entity is None:
                    continue
                canon_state = str(entity["canon_state"])
                common["entity_id"] = str(entity["id"])
                common["evidence"] = {
                    **common["evidence"],
                    "entity_name": entity["canonical_name"],
                    "canon_state": canon_state,
                }
                if canon_state == CanonState.INFERENCE.value:
                    self._append(
                        findings,
                        config,
                        rule_id="reference_inference",
                        message=f"「{entity['canonical_name']}」はINFERENCEのまま本文から参照されています。",
                        **common,
                    )
                elif canon_state == CanonState.DISPUTED.value:
                    self._append(
                        findings,
                        config,
                        rule_id="reference_disputed",
                        message=f"「{entity['canonical_name']}」はDISPUTED状態です。",
                        **common,
                    )
                elif canon_state == CanonState.DEPRECATED.value:
                    self._append(
                        findings,
                        config,
                        rule_id="reference_deprecated",
                        message=f"「{entity['canonical_name']}」はDEPRECATED状態です。",
                        **common,
                    )
                elif canon_state in {CanonState.ARCHIVED.value, CanonState.REJECTED.value}:
                    self._append(
                        findings,
                        config,
                        rule_id="reference_inactive",
                        message=f"「{entity['canonical_name']}」は{canon_state}状態ですが本文から参照されています。",
                        **common,
                    )

        custom_terms = config.get("custom_terms", [])
        if isinstance(custom_terms, list):
            folded_content = content.casefold()
            for index, item in enumerate(custom_terms):
                if not isinstance(item, dict) or item.get("enabled", True) is False:
                    continue
                term = str(item.get("term", "")).strip()
                if not term:
                    continue
                case_sensitive = bool(item.get("case_sensitive", False))
                haystack = content if case_sensitive else folded_content
                needle = term if case_sensitive else term.casefold()
                start = 0
                while True:
                    found = haystack.find(needle, start)
                    if found < 0:
                        break
                    end = found + len(term)
                    rule_id = f"custom_term:{item.get('id') or index}"
                    severity = str(item.get("severity", "warning"))
                    if severity not in SEVERITIES:
                        severity = "warning"
                    findings.append(
                        self._finding(
                            rule_id=rule_id,
                            category="custom",
                            severity=severity,
                            document_id=document_id,
                            entity_id=None,
                            message=str(item.get("message") or f"カスタム禁止語「{term}」が本文に含まれています。"),
                            start_offset=found,
                            end_offset=end,
                            evidence={"term": term, "case_sensitive": case_sensitive},
                        )
                    )
                    start = max(end, found + 1)

        findings.extend(self._isekai_document_findings(project_id, document, config))
        return findings

    def _project_findings(
        self,
        project_id: UUID,
        config: dict[str, object],
    ) -> list[dict[str, object]]:
        findings: list[dict[str, object]] = []
        bible = self.bible.list(project_id)
        bible_by_id = {str(item["id"]): item for item in bible}

        names: dict[str, list[dict[str, object]]] = defaultdict(list)
        for entity in bible:
            names[normalize_key(str(entity["canonical_name"]))].append(entity)
        for normalized, group in names.items():
            if normalized and len(group) > 1:
                ids = [str(item["id"]) for item in group]
                self._append(
                    findings,
                    config,
                    rule_id="canonical_name_collision",
                    message="同一の正規化正式名称を持つBibleエンティティが複数あります: " + " / ".join(str(item["canonical_name"]) for item in group),
                    evidence={"normalized_name": normalized, "entity_ids": ids},
                )

        aliases: dict[str, set[str]] = defaultdict(set)
        alias_surfaces: dict[str, set[str]] = defaultdict(set)
        for alias in self.entities.list_aliases(project_id):
            normalized = str(alias["normalized_alias"])
            aliases[normalized].add(str(alias["entity_id"]))
            alias_surfaces[normalized].add(str(alias["alias"]))
        for normalized, ids in aliases.items():
            if normalized and len(ids) > 1:
                self._append(
                    findings,
                    config,
                    rule_id="alias_collision",
                    message="同じ別名が複数エンティティへ割り当てられています: " + " / ".join(sorted(alias_surfaces[normalized])),
                    evidence={"normalized_alias": normalized, "entity_ids": sorted(ids)},
                )

        for event in self.timeline.list(project_id):
            if str(event["canon_state"]) != CanonState.CANON.value:
                continue
            noncanon = []
            for participant_id in event["participant_ids"]:
                entity = bible_by_id.get(str(participant_id))
                if entity is not None and str(entity["canon_state"]) != CanonState.CANON.value:
                    noncanon.append({"id": entity["id"], "name": entity["canonical_name"], "state": entity["canon_state"]})
            if noncanon:
                self._append(
                    findings,
                    config,
                    rule_id="canon_timeline_noncanon_participant",
                    message=f"CANON時系列「{event['title']}」が非CANON参加者を参照しています。",
                    evidence={"timeline_event_id": event["id"], "participants": noncanon},
                )

        for relation in self.entities.list_relations(project_id):
            if str(relation["canon_state"]) != CanonState.CANON.value:
                continue
            endpoints = [
                bible_by_id.get(str(relation["source_entity_id"])),
                bible_by_id.get(str(relation["target_entity_id"])),
            ]
            noncanon = [
                {"id": item["id"], "name": item["canonical_name"], "state": item["canon_state"]}
                for item in endpoints
                if item is not None and str(item["canon_state"]) != CanonState.CANON.value
            ]
            if noncanon:
                self._append(
                    findings,
                    config,
                    rule_id="canon_relation_noncanon_endpoint",
                    message=f"CANON関係「{relation['label'] or relation['relation_type']}」の端点に非CANON設定があります。",
                    evidence={"relation_id": relation["id"], "endpoints": noncanon},
                )

        findings.extend(self._isekai_project_findings(project_id, config, bible))
        findings.extend(self._ln_genre_project_findings(project_id, config, bible, bible_by_id))
        return findings

    def _ln_genre_project_findings(
        self,
        project_id: UUID,
        lint_config: dict[str, object],
        bible: list[dict[str, object]],
        bible_by_id: dict[str, dict[str, object]],
    ) -> list[dict[str, object]]:
        pack = self.ln_genres.get(project_id)
        if pack is None:
            return []
        enabled = pack.get("enabled_packs", {})
        findings: list[dict[str, object]] = []
        relations = self.entities.list_relations(project_id)

        if isinstance(enabled, dict) and bool(enabled.get("noble_lady", False)):
            findings.extend(self._noble_findings(
                lint_config,
                bible,
                bible_by_id,
                relations,
                pack.get("noble_lady", {}),
            ))
        if isinstance(enabled, dict) and bool(enabled.get("palace_harem", False)):
            findings.extend(self._palace_findings(
                lint_config,
                bible,
                bible_by_id,
                pack.get("palace_harem", {}),
            ))
        if isinstance(enabled, dict) and bool(enabled.get("romcom", False)):
            findings.extend(self._romcom_findings(
                lint_config,
                bible,
                pack.get("romcom", {}),
            ))
        return findings

    def _noble_findings(
        self,
        lint_config: dict[str, object],
        bible: list[dict[str, object]],
        bible_by_id: dict[str, dict[str, object]],
        relations: list[dict[str, object]],
        policy: object,
    ) -> list[dict[str, object]]:
        if not isinstance(policy, dict):
            return []
        findings: list[dict[str, object]] = []
        ranks = [str(item) for item in policy.get("rank_order", [])]
        rank_title_map = policy.get("rank_title_map", {})
        rank_title_map = rank_title_map if isinstance(rank_title_map, dict) else {}
        noble_by_id: dict[str, dict[str, object]] = {}

        for entity in bible:
            if str(entity.get("entity_type")) != "character":
                continue
            attributes = entity.get("attributes", {})
            if not isinstance(attributes, dict):
                continue
            noble = attributes.get("ln_noble")
            if not isinstance(noble, dict):
                continue
            entity_id = str(entity["id"])
            noble_by_id[entity_id] = noble
            rank = str(noble.get("rank", "")).strip()
            if rank and rank not in ranks:
                self._append(
                    findings,
                    lint_config,
                    rule_id="noble_rank_unknown",
                    entity_id=entity_id,
                    message=f"「{entity['canonical_name']}」の爵位「{rank}」は爵位序列にありません。",
                    evidence={"rank": rank, "rank_order": ranks, "pack": "noble_lady"},
                )
            house_id = str(noble.get("house_entity_id", "")).strip()
            if house_id and house_id not in bible_by_id:
                self._append(
                    findings,
                    lint_config,
                    rule_id="noble_house_reference_invalid",
                    entity_id=entity_id,
                    message=f"「{entity['canonical_name']}」の所属家参照がStory Bibleに存在しません。",
                    evidence={"house_entity_id": house_id, "pack": "noble_lady"},
                )
            public_title = str(noble.get("public_title", "")).strip()
            allowed_titles = rank_title_map.get(rank, [])
            if (
                public_title
                and isinstance(allowed_titles, list)
                and allowed_titles
                and public_title not in {str(item) for item in allowed_titles}
            ):
                self._append(
                    findings,
                    lint_config,
                    rule_id="noble_title_rank_mismatch",
                    entity_id=entity_id,
                    message=f"「{entity['canonical_name']}」の公開称号「{public_title}」は爵位「{rank}」の許可称号にありません。",
                    evidence={"rank": rank, "public_title": public_title, "allowed_titles": allowed_titles, "pack": "noble_lady"},
                )

        relation_types = {str(item) for item in policy.get("engagement_relation_types", [])}
        if not bool(policy.get("allow_multiple_active_engagements", False)) and relation_types:
            active: dict[str, list[dict[str, object]]] = defaultdict(list)
            for relation in relations:
                if str(relation.get("relation_type")) not in relation_types:
                    continue
                attributes = relation.get("attributes", {})
                status = str(attributes.get("status", "active")) if isinstance(attributes, dict) else "active"
                if status != "active":
                    continue
                active[str(relation["source_entity_id"])].append(relation)
                active[str(relation["target_entity_id"])].append(relation)
            for entity_id, group in active.items():
                if len(group) > 1:
                    entity = bible_by_id.get(entity_id)
                    name = str(entity["canonical_name"]) if entity else entity_id
                    self._append(
                        findings,
                        lint_config,
                        rule_id="noble_multiple_active_engagements",
                        entity_id=entity_id if entity else None,
                        message=f"「{name}」に有効な婚約関係が{len(group)}件あります。",
                        evidence={"relation_ids": [item["id"] for item in group], "pack": "noble_lady"},
                    )

        address_rules = policy.get("address_rules", [])
        if isinstance(address_rules, list):
            rules_by_rank = {
                str(item.get("target_rank")): {str(v) for v in item.get("allowed_addresses", [])}
                for item in address_rules
                if isinstance(item, dict)
            }
            for event in bible:
                attributes = event.get("attributes", {})
                if not isinstance(attributes, dict):
                    continue
                address = attributes.get("ln_address")
                if not isinstance(address, dict):
                    continue
                target_id = str(address.get("target_entity_id", ""))
                used = str(address.get("used_address", "")).strip()
                target = bible_by_id.get(target_id)
                target_noble = noble_by_id.get(target_id)
                if target is None or target_noble is None:
                    continue
                target_rank = str(target_noble.get("rank", ""))
                allowed = rules_by_rank.get(target_rank)
                if allowed and used and used not in allowed:
                    self._append(
                        findings,
                        lint_config,
                        rule_id="noble_address_mismatch",
                        entity_id=str(event["id"]),
                        message=f"呼称イベント「{event['canonical_name']}」の「{used}」は対象爵位「{target_rank}」の許可呼称にありません。",
                        evidence={"address": address, "allowed_addresses": sorted(allowed), "pack": "noble_lady"},
                    )

        return findings

    def _palace_findings(
        self,
        lint_config: dict[str, object],
        bible: list[dict[str, object]],
        bible_by_id: dict[str, dict[str, object]],
        policy: object,
    ) -> list[dict[str, object]]:
        if not isinstance(policy, dict):
            return []
        findings: list[dict[str, object]] = []
        ranks = [str(item) for item in policy.get("rank_order", [])]
        rank_index = {rank: index for index, rank in enumerate(ranks)}
        palace_by_id: dict[str, dict[str, object]] = {}

        for entity in bible:
            if str(entity.get("entity_type")) != "character":
                continue
            attributes = entity.get("attributes", {})
            if not isinstance(attributes, dict):
                continue
            palace = attributes.get("ln_palace")
            if not isinstance(palace, dict):
                continue
            entity_id = str(entity["id"])
            palace_by_id[entity_id] = palace
            rank = str(palace.get("rank", "")).strip()
            if rank and rank not in rank_index:
                self._append(
                    findings,
                    lint_config,
                    rule_id="palace_rank_unknown",
                    entity_id=entity_id,
                    message=f"「{entity['canonical_name']}」の位階「{rank}」は宮廷位階序列にありません。",
                    evidence={"rank": rank, "rank_order": ranks, "pack": "palace_harem"},
                )
            faction_id = str(palace.get("faction_entity_id", "")).strip()
            if faction_id and faction_id not in bible_by_id:
                self._append(
                    findings,
                    lint_config,
                    rule_id="palace_faction_reference_invalid",
                    entity_id=entity_id,
                    message=f"「{entity['canonical_name']}」の派閥参照がStory Bibleに存在しません。",
                    evidence={"faction_entity_id": faction_id, "pack": "palace_harem"},
                )

        restricted = {
            str(item.get("place_entity_id")): item
            for item in policy.get("restricted_areas", [])
            if isinstance(item, dict)
        }
        information = {
            str(item.get("fact_key")): item
            for item in policy.get("information_rules", [])
            if isinstance(item, dict)
        }

        def authorized(actor_id: str, rule: dict[str, object]) -> bool:
            if actor_id in {str(item) for item in rule.get("exception_entity_ids", [])}:
                return True
            actor = palace_by_id.get(actor_id, {})
            actor_rank = str(actor.get("rank", ""))
            min_rank = str(rule.get("min_rank", ""))
            if min_rank:
                if actor_rank not in rank_index or rank_index[actor_rank] < rank_index.get(min_rank, len(ranks)):
                    return False
            allowed_factions = {str(item) for item in rule.get("allowed_faction_entity_ids", [])}
            if allowed_factions:
                return str(actor.get("faction_entity_id", "")) in allowed_factions
            return True

        ritual_events: dict[str, list[tuple[int, dict[str, object], dict[str, object]]]] = defaultdict(list)
        for event in bible:
            attributes = event.get("attributes", {})
            if not isinstance(attributes, dict):
                continue
            access = attributes.get("ln_palace_access")
            if isinstance(access, dict):
                actor_id = str(access.get("actor_entity_id", ""))
                place_id = str(access.get("place_entity_id", ""))
                rule = restricted.get(place_id)
                if rule is not None and not authorized(actor_id, rule):
                    actor = bible_by_id.get(actor_id)
                    place = bible_by_id.get(place_id)
                    self._append(
                        findings,
                        lint_config,
                        rule_id="palace_restricted_area_access",
                        entity_id=str(event["id"]),
                        message=f"「{actor['canonical_name'] if actor else actor_id}」は「{place['canonical_name'] if place else place_id}」の立入条件を満たしていません。",
                        evidence={"access": access, "rule": rule, "pack": "palace_harem"},
                    )
            info_access = attributes.get("ln_information_access")
            if isinstance(info_access, dict):
                actor_id = str(info_access.get("actor_entity_id", ""))
                fact_key = str(info_access.get("fact_key", ""))
                rule = information.get(fact_key)
                if rule is not None and not authorized(actor_id, rule):
                    actor = bible_by_id.get(actor_id)
                    self._append(
                        findings,
                        lint_config,
                        rule_id="palace_information_access",
                        entity_id=str(event["id"]),
                        message=f"「{actor['canonical_name'] if actor else actor_id}」は情報「{fact_key}」のアクセス条件を満たしていません。",
                        evidence={"information_access": info_access, "rule": rule, "pack": "palace_harem"},
                    )
            ritual = attributes.get("ln_ritual")
            if isinstance(ritual, dict):
                key = str(ritual.get("ritual_key", "")).strip()
                try:
                    sequence = int(ritual.get("sequence_index", 0))
                except (TypeError, ValueError):
                    sequence = 0
                if key:
                    ritual_events[key].append((sequence, event, ritual))

        sequences = {
            str(item.get("ritual_key")): [str(step) for step in item.get("steps", [])]
            for item in policy.get("ritual_sequences", [])
            if isinstance(item, dict)
        }
        for ritual_key, events in ritual_events.items():
            expected = sequences.get(ritual_key)
            if not expected:
                continue
            positions = {step: index for index, step in enumerate(expected)}
            observed_positions: list[int] = []
            for _, event, ritual in sorted(events, key=lambda item: item[0]):
                step = str(ritual.get("step_key", ""))
                if step not in positions:
                    self._append(
                        findings,
                        lint_config,
                        rule_id="palace_ritual_step_unknown",
                        entity_id=str(event["id"]),
                        message=f"儀礼「{ritual_key}」に未定義手順「{step}」があります。",
                        evidence={"ritual": ritual, "expected_steps": expected, "pack": "palace_harem"},
                    )
                    continue
                observed_positions.append(positions[step])
            if any(later <= earlier for earlier, later in zip(observed_positions, observed_positions[1:])):
                self._append(
                    findings,
                    lint_config,
                    rule_id="palace_ritual_order",
                    message=f"儀礼「{ritual_key}」の手順順序が設定済み順序と一致しません。",
                    evidence={"observed_positions": observed_positions, "expected_steps": expected, "pack": "palace_harem"},
                )

        return findings

    def _romcom_findings(
        self,
        lint_config: dict[str, object],
        bible: list[dict[str, object]],
        policy: object,
    ) -> list[dict[str, object]]:
        if not isinstance(policy, dict):
            return []
        findings: list[dict[str, object]] = []
        stages = [str(item) for item in policy.get("stages", [])]
        stage_index = {stage: index for index, stage in enumerate(stages)}
        max_jump = int(policy.get("max_stage_jump", 1))
        schedule_by_participant: dict[tuple[str, str], list[tuple[int, int, dict[str, object]]]] = defaultdict(list)
        misunderstandings: dict[str, list[tuple[int, str, dict[str, object]]]] = defaultdict(list)

        for event in bible:
            attributes = event.get("attributes", {})
            if not isinstance(attributes, dict):
                continue
            transition = attributes.get("ln_relationship_transition")
            if isinstance(transition, dict):
                before = str(transition.get("from_stage", ""))
                after = str(transition.get("to_stage", ""))
                if before not in stage_index or after not in stage_index:
                    self._append(
                        findings,
                        lint_config,
                        rule_id="romcom_stage_unknown",
                        entity_id=str(event["id"]),
                        message=f"関係遷移イベント「{event['canonical_name']}」に未定義段階があります。",
                        evidence={"transition": transition, "stages": stages, "pack": "romcom"},
                    )
                else:
                    delta = stage_index[after] - stage_index[before]
                    if delta > max_jump:
                        reason = str(transition.get("reason", "")).strip()
                        suffix = " 理由が未記入です。" if bool(policy.get("require_reason_for_large_jump", True)) and not reason else ""
                        self._append(
                            findings,
                            lint_config,
                            rule_id="romcom_stage_jump",
                            entity_id=str(event["id"]),
                            message=f"「{event['canonical_name']}」は関係段階を{delta}段階進めています。許容は{max_jump}段階です。{suffix}",
                            evidence={"transition": transition, "delta": delta, "max_stage_jump": max_jump, "pack": "romcom"},
                        )
                    if delta < 0 and not bool(policy.get("allow_regression", True)):
                        self._append(
                            findings,
                            lint_config,
                            rule_id="romcom_stage_regression",
                            entity_id=str(event["id"]),
                            message=f"「{event['canonical_name']}」で関係段階が「{before}」から「{after}」へ後退しています。",
                            evidence={"transition": transition, "pack": "romcom"},
                        )

            schedule = attributes.get("ln_schedule")
            if isinstance(schedule, dict):
                day = str(schedule.get("day_key", "")).strip()
                try:
                    start = int(schedule.get("start_minute"))
                    end = int(schedule.get("end_minute"))
                except (TypeError, ValueError):
                    start = end = -1
                participants = schedule.get("participant_ids", [])
                if not isinstance(participants, list) or start < 0 or end <= start:
                    self._append(
                        findings,
                        lint_config,
                        rule_id="romcom_schedule_invalid",
                        entity_id=str(event["id"]),
                        message=f"予定イベント「{event['canonical_name']}」の時間情報が不正です。",
                        evidence={"schedule": schedule, "pack": "romcom"},
                    )
                else:
                    for participant_id in participants:
                        schedule_by_participant[(str(participant_id), day)].append((start, end, event))

            misunderstanding = attributes.get("ln_misunderstanding")
            if isinstance(misunderstanding, dict):
                key = str(misunderstanding.get("misunderstanding_id", "")).strip()
                action = str(misunderstanding.get("action", "")).strip()
                try:
                    sequence = int(misunderstanding.get("sequence_index", 0))
                except (TypeError, ValueError):
                    sequence = 0
                if key:
                    misunderstandings[key].append((sequence, action, event))

        for (participant_id, day), events in schedule_by_participant.items():
            ordered = sorted(events, key=lambda item: (item[0], item[1]))
            previous: tuple[int, int, dict[str, object]] | None = None
            for current in ordered:
                if previous is not None and current[0] < previous[1]:
                    self._append(
                        findings,
                        lint_config,
                        rule_id="romcom_schedule_conflict",
                        entity_id=str(current[2]["id"]),
                        message=f"同一人物の予定「{previous[2]['canonical_name']}」と「{current[2]['canonical_name']}」が{day}で重複しています。",
                        evidence={
                            "participant_id": participant_id,
                            "day_key": day,
                            "first_event_id": previous[2]["id"],
                            "second_event_id": current[2]["id"],
                            "first_range": [previous[0], previous[1]],
                            "second_range": [current[0], current[1]],
                            "pack": "romcom",
                        },
                    )
                if previous is None or current[1] > previous[1]:
                    previous = current

        unresolved_severity = str(policy.get("unresolved_misunderstanding_severity", "info"))
        for key, actions in misunderstandings.items():
            open_state = False
            for _, action, event in sorted(actions, key=lambda item: item[0]):
                if action == "open":
                    if open_state:
                        self._append(
                            findings,
                            lint_config,
                            rule_id="romcom_misunderstanding_order",
                            entity_id=str(event["id"]),
                            message=f"誤解「{key}」が解消前に再度OPENされています。",
                            evidence={"misunderstanding_id": key, "action": action, "pack": "romcom"},
                        )
                    open_state = True
                elif action == "resolve":
                    if not open_state:
                        self._append(
                            findings,
                            lint_config,
                            rule_id="romcom_misunderstanding_order",
                            entity_id=str(event["id"]),
                            message=f"誤解「{key}」がOPENされる前にRESOLVEされています。",
                            evidence={"misunderstanding_id": key, "action": action, "pack": "romcom"},
                        )
                    open_state = False
                else:
                    self._append(
                        findings,
                        lint_config,
                        rule_id="romcom_misunderstanding_order",
                        entity_id=str(event["id"]),
                        message=f"誤解「{key}」に未知のaction「{action}」があります。",
                        evidence={"misunderstanding_id": key, "action": action, "pack": "romcom"},
                    )
            if open_state:
                self._append(
                    findings,
                    lint_config,
                    rule_id="romcom_misunderstanding_unresolved",
                    message=f"誤解「{key}」がまだ解消されていません。",
                    evidence={"misunderstanding_id": key, "pack": "romcom"},
                    severity_override=unresolved_severity,
                )

        return findings

    def _isekai_document_findings(
        self,
        project_id: UUID,
        document: dict[str, object],
        lint_config: dict[str, object],
    ) -> list[dict[str, object]]:
        pack = self.isekai.get(project_id)
        if pack is None or not bool(pack.get("enabled", False)):
            return []

        content = str(document.get("content", ""))
        document_id = str(document["id"])
        if not content:
            return []

        strictness = str(pack.get("strictness", "standard"))
        default_severity = STRICTNESS_TO_SEVERITY.get(strictness, "warning")
        enabled_categories = pack.get("enabled_categories", {})
        allow_terms = {normalize_key(str(item)) for item in pack.get("allow_terms", [])}
        replacements = {
            normalize_key(str(item.get("earth_term", ""))): item
            for item in pack.get("replacements", [])
            if isinstance(item, dict)
        }

        entries: list[dict[str, object]] = [dict(item) for item in EARTH_TERM_CATALOG]
        for item in pack.get("custom_terms", []):
            if isinstance(item, dict) and item.get("enabled", True):
                entries.append(dict(item))

        findings: list[dict[str, object]] = []
        seen_spans: set[tuple[int, int, str]] = set()

        for entry in entries:
            term = str(entry.get("term", "")).strip()
            category = str(entry.get("category", ""))
            if not term or not bool(enabled_categories.get(category, True)):
                continue
            normalized_term = normalize_key(term)
            if normalized_term in allow_terms:
                continue
            flags = re.IGNORECASE if term.isascii() else 0
            for match in re.finditer(re.escape(term), content, flags):
                found, end = match.span()
                span_key = (found, end, normalized_term)
                if span_key in seen_spans:
                    continue
                seen_spans.add(span_key)
                replacement = replacements.get(normalized_term)
                world_term = str(replacement.get("world_term")) if replacement else None
                generic = str(entry.get("generic_replacement", "")) or None
                severity_override = str(entry.get("severity")) if entry.get("severity") else default_severity
                self._append(
                    findings,
                    lint_config,
                    rule_id="isekai_earth_origin_term",
                    message=(
                        f"異世界感ガード: 「{content[found:end]}」は地球由来語候補です。"
                        + (f" 世界内候補「{world_term}」が登録されています。" if world_term else "")
                        + (f" 一般化候補は「{generic}」です。" if generic else "")
                    ),
                    document_id=document_id,
                    start_offset=found,
                    end_offset=end,
                    evidence={
                        "term": term,
                        "category": category,
                        "concept_key": entry.get("concept_key"),
                        "generic_replacement": generic,
                        "world_replacement": world_term,
                        "source_place_entity_id": replacement.get("source_place_entity_id") if replacement else None,
                        "strictness": strictness,
                        "pack": "isekai",
                    },
                    severity_override=severity_override,
                )
                if bool(pack.get("require_world_mapping", False)) and replacement is None:
                    self._append(
                        findings,
                        lint_config,
                        rule_id="isekai_world_term_unmapped",
                        message=f"「{content[found:end]}」には承認済みの世界内名称がまだありません。",
                        document_id=document_id,
                        start_offset=found,
                        end_offset=end,
                        evidence={
                            "term": term,
                            "category": category,
                            "concept_key": entry.get("concept_key"),
                            "generic_replacement": generic,
                            "pack": "isekai",
                        },
                    )

        return findings

    def _isekai_project_findings(
        self,
        project_id: UUID,
        lint_config: dict[str, object],
        bible: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        pack = self.isekai.get(project_id)
        if pack is None or not bool(pack.get("enabled", False)):
            return []

        findings: list[dict[str, object]] = []
        routes = [item for item in pack.get("travel_routes", []) if isinstance(item, dict)]
        magic_policy = pack.get("magic_policy", {})
        economy_policy = pack.get("economy_policy", {})
        healing_policy = pack.get("healing_policy", {})

        for entity in bible:
            attributes = entity.get("attributes", {})
            if not isinstance(attributes, dict):
                continue
            entity_id = str(entity["id"])
            entity_name = str(entity["canonical_name"])

            travel = attributes.get("isekai_travel")
            if isinstance(travel, dict):
                from_id = str(travel.get("from_entity_id", ""))
                to_id = str(travel.get("to_entity_id", ""))
                mode = str(travel.get("mode", ""))
                try:
                    duration = float(travel.get("duration_hours"))
                except (TypeError, ValueError):
                    duration = None
                matches: list[dict[str, object]] = []
                for route in routes:
                    direct = (
                        str(route.get("from_entity_id")) == from_id
                        and str(route.get("to_entity_id")) == to_id
                    )
                    reverse = (
                        bool(route.get("bidirectional", True))
                        and str(route.get("from_entity_id")) == to_id
                        and str(route.get("to_entity_id")) == from_id
                    )
                    if (direct or reverse) and str(route.get("mode")) == mode:
                        matches.append(route)
                if routes and not matches:
                    self._append(
                        findings,
                        lint_config,
                        rule_id="isekai_travel_route_unknown",
                        entity_id=entity_id,
                        message=f"移動イベント「{entity_name}」に対応するルート規則がありません。",
                        evidence={"travel": travel, "pack": "isekai"},
                    )
                elif matches and duration is not None:
                    route = matches[0]
                    minimum = float(route.get("min_hours", 0))
                    maximum = float(route.get("max_hours", 0))
                    if duration < minimum or duration > maximum:
                        self._append(
                            findings,
                            lint_config,
                            rule_id="isekai_travel_duration",
                            entity_id=entity_id,
                            message=f"移動イベント「{entity_name}」の所要時間 {duration:g}h は設定範囲 {minimum:g}–{maximum:g}h 外です。",
                            evidence={"travel": travel, "route": route, "pack": "isekai"},
                        )

            if str(entity.get("entity_type")) == "spell":
                magic = attributes.get("magic")
                if isinstance(magic_policy, dict) and bool(magic_policy.get("enabled", False)):
                    magic = magic if isinstance(magic, dict) else {}
                    cost = magic.get("cost")
                    tier = str(magic.get("tier", ""))
                    costless_tiers = {str(item) for item in magic_policy.get("costless_tiers", [])}
                    if bool(magic_policy.get("require_cost", True)) and not isinstance(cost, dict) and tier not in costless_tiers:
                        self._append(
                            findings,
                            lint_config,
                            rule_id="isekai_magic_cost_missing",
                            entity_id=entity_id,
                            message=f"呪文「{entity_name}」に魔法コストが設定されていません。",
                            evidence={"tier": tier, "magic": magic, "pack": "isekai"},
                        )
                    if isinstance(cost, dict):
                        cost_type = str(cost.get("type", ""))
                        allowed = {str(item) for item in magic_policy.get("allowed_cost_types", [])}
                        if allowed and cost_type not in allowed:
                            self._append(
                                findings,
                                lint_config,
                                rule_id="isekai_magic_cost_type",
                                entity_id=entity_id,
                                message=f"呪文「{entity_name}」のコスト種別「{cost_type}」は許可一覧にありません。",
                                evidence={"cost": cost, "allowed_cost_types": sorted(allowed), "pack": "isekai"},
                            )

                healing = attributes.get("healing")
                if isinstance(healing_policy, dict) and bool(healing_policy.get("enabled", False)) and isinstance(healing, dict):
                    violations: list[str] = []
                    if bool(healing.get("resurrection", False)) and not bool(healing_policy.get("resurrection_allowed", False)):
                        violations.append("死者蘇生")
                    if bool(healing.get("limb_regrowth", False)) and not bool(healing_policy.get("limb_regrowth_allowed", False)):
                        violations.append("欠損再生")
                    if violations:
                        self._append(
                            findings,
                            lint_config,
                            rule_id="isekai_healing_limit",
                            entity_id=entity_id,
                            message=f"治癒魔法「{entity_name}」が設定上許可されていない能力（{'・'.join(violations)}）を持っています。",
                            evidence={"healing": healing, "policy": healing_policy, "pack": "isekai"},
                        )

            if str(entity.get("entity_type")) == "item" and isinstance(economy_policy, dict) and bool(economy_policy.get("enabled", False)):
                economy = attributes.get("economy")
                if isinstance(economy, dict):
                    currency = str(economy.get("currency", ""))
                    category = str(economy.get("category", ""))
                    try:
                        price = float(economy.get("price"))
                    except (TypeError, ValueError):
                        price = None
                    currencies = {str(item) for item in economy_policy.get("currencies", [])}
                    if currency and currencies and currency not in currencies:
                        self._append(
                            findings,
                            lint_config,
                            rule_id="isekai_currency_unregistered",
                            entity_id=entity_id,
                            message=f"アイテム「{entity_name}」の通貨「{currency}」は世界経済設定に登録されていません。",
                            evidence={"economy": economy, "currencies": sorted(currencies), "pack": "isekai"},
                        )
                    if price is not None:
                        for band in economy_policy.get("price_bands", []):
                            if not isinstance(band, dict):
                                continue
                            if str(band.get("category")) != category or str(band.get("currency")) != currency:
                                continue
                            minimum = float(band.get("min_price", 0))
                            maximum = float(band.get("max_price", 0))
                            if price < minimum or price > maximum:
                                self._append(
                                    findings,
                                    lint_config,
                                    rule_id="isekai_price_out_of_band",
                                    entity_id=entity_id,
                                    message=f"アイテム「{entity_name}」の価格 {price:g} {currency} は設定帯 {minimum:g}–{maximum:g} 外です。",
                                    evidence={"economy": economy, "price_band": band, "pack": "isekai"},
                                )
                            break

        return findings

    def _append(
        self,
        findings: list[dict[str, object]],
        config: dict[str, object],
        *,
        rule_id: str,
        message: str,
        document_id: str | None = None,
        entity_id: str | None = None,
        start_offset: int | None = None,
        end_offset: int | None = None,
        evidence: dict[str, object] | None = None,
        severity_override: str | None = None,
    ) -> None:
        rule_config = {}
        builtins = config.get("builtins", {})
        if isinstance(builtins, dict):
            candidate = builtins.get(rule_id, {})
            if isinstance(candidate, dict):
                rule_config = candidate
        if rule_config.get("enabled", True) is False:
            return
        spec = BUILTIN_RULES[rule_id]
        if "severity" in rule_config:
            severity = str(rule_config["severity"])
        elif severity_override is not None:
            severity = str(severity_override)
        else:
            severity = str(spec["default_severity"])
        if severity not in SEVERITIES:
            severity = str(spec["default_severity"])
        findings.append(
            self._finding(
                rule_id=rule_id,
                category=str(spec["category"]),
                severity=severity,
                document_id=document_id,
                entity_id=entity_id,
                message=message,
                start_offset=start_offset,
                end_offset=end_offset,
                evidence=evidence or {},
            )
        )

    @staticmethod
    def _finding(
        *,
        rule_id: str,
        category: str,
        severity: str,
        document_id: str | None,
        entity_id: str | None,
        message: str,
        start_offset: int | None,
        end_offset: int | None,
        evidence: dict[str, object],
    ) -> dict[str, object]:
        return {
            "rule_id": rule_id,
            "category": category,
            "severity": severity,
            "document_id": document_id,
            "entity_id": entity_id,
            "message": message,
            "start_offset": start_offset,
            "end_offset": end_offset,
            "evidence": evidence,
            "fingerprint": fingerprint([
                rule_id,
                document_id,
                entity_id,
                start_offset,
                end_offset,
                evidence,
            ]),
        }

    @staticmethod
    def _summary(findings: list[dict[str, object]]) -> dict[str, object]:
        severities = Counter(str(item["severity"]) for item in findings)
        categories = Counter(str(item["category"]) for item in findings)
        return {
            "total": len(findings),
            "by_severity": dict(severities),
            "by_category": dict(categories),
        }

    @staticmethod
    def _validate_config(rules: dict[str, object]) -> dict[str, object]:
        builtins = rules.get("builtins", {})
        custom_terms = rules.get("custom_terms", [])
        if not isinstance(builtins, dict):
            raise ValueError("rules.builtins must be an object")
        if not isinstance(custom_terms, list):
            raise ValueError("rules.custom_terms must be a list")

        cleaned_builtins: dict[str, object] = {}
        for rule_id, value in builtins.items():
            if rule_id not in BUILTIN_RULES:
                raise ValueError(f"Unknown builtin lint rule: {rule_id}")
            if not isinstance(value, dict):
                raise ValueError("Builtin lint rule config must be an object")
            severity = str(value.get("severity", BUILTIN_RULES[rule_id]["default_severity"]))
            if severity not in SEVERITIES:
                raise ValueError(f"Unknown lint severity: {severity}")
            cleaned_builtins[rule_id] = {
                "enabled": bool(value.get("enabled", True)),
                "severity": severity,
            }

        cleaned_terms: list[dict[str, object]] = []
        for index, item in enumerate(custom_terms):
            if not isinstance(item, dict):
                raise ValueError("Custom term rule must be an object")
            term = str(item.get("term", "")).strip()
            if not term or len(term) > 200:
                raise ValueError("Custom term must be 1-200 characters")
            severity = str(item.get("severity", "warning"))
            if severity not in SEVERITIES:
                raise ValueError(f"Unknown lint severity: {severity}")
            cleaned_terms.append({
                "id": str(item.get("id") or f"term-{index + 1}")[:100],
                "term": term,
                "severity": severity,
                "enabled": bool(item.get("enabled", True)),
                "case_sensitive": bool(item.get("case_sensitive", False)),
                "message": str(item.get("message", ""))[:1000],
            })

        return {"builtins": cleaned_builtins, "custom_terms": cleaned_terms}
