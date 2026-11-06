"""PRISM Topic Bank: deterministic prototype, no external model dependency."""
import hashlib
import re
import unicodedata

REQUIRED = ("全頭診断", "コース・馬場・展開", "調教・映像・取材", "全AI本命プレゼン", "全AI買い目・反論")
CATEGORIES = ("能力", "展開", "馬場", "コース", "枠", "騎手", "血統", "調教", "馬体", "映像", "厩舎", "オッズ", "買い目", "不利", "状態", "ローテ", "反実仮想", "少数意見", "結果検証")

def normalize_topic(value):
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\s\W_]+", "", value, flags=re.UNICODE)

def topic_id(category, hypothesis, scope=""):
    canonical = "|".join(map(normalize_topic, (category, hypothesis, scope)))
    return "TOP-" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]

def create_topic(category, hypothesis, scope, origin_agent, falsifier, evidence_required):
    if category not in CATEGORIES or not all((hypothesis, scope, origin_agent, falsifier, evidence_required)):
        raise ValueError("INVALID_TOPIC")
    return {"topic_id":topic_id(category,hypothesis,scope), "category":category,
        "hypothesis":hypothesis, "scope":scope, "origin_agent":origin_agent,
        "falsifier":falsifier, "evidence_required":evidence_required,
        "status":"candidate", "usage_count":0, "result_reviews":0}

def add_candidate(bank, topic):
    """Reject exact canonical duplicates. Semantic dedupe needs human/model review."""
    if any(t["topic_id"] == topic["topic_id"] for t in bank):
        return {"status":"duplicate", "topic_id":topic["topic_id"]}
    bank.append(topic)
    return {"status":"candidate", "topic_id":topic["topic_id"]}

def coverage_gate(roundtable):
    topics = roundtable.get("topics", [])
    covered = {t.get("theme") for t in topics if t.get("utterances") and t.get("evidence_status")}
    missing = [theme for theme in REQUIRED if theme not in covered]
    participants = roundtable.get("participants", [])
    missing_agents = [a.get("agent_id") for a in participants
                      if not a.get("marks") or not (a.get("tickets") or a.get("pass_reason"))]
    return {"complete":not missing and not missing_agents and bool(participants),
            "missing_themes":missing, "missing_agent_conclusions":missing_agents,
            "theme_count":len(covered)}
