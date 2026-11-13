"""PRISM pre-day publication gate. No fabricated expert executions."""
from datetime import datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")

def check_publication(race, preliminary, discussions, final, published_at):
    """Return actionable errors; never infer an AI run from simulated dialogue."""
    errors = []
    start = datetime.fromisoformat(race["start_at"])
    published = datetime.fromisoformat(published_at)
    if start.tzinfo is None or published.tzinfo is None:
        raise ValueError("timezone-aware timestamps required")
    local_start, local_published = start.astimezone(JST), published.astimezone(JST)
    if local_published.date() >= local_start.date():
        errors.append("LATE_PUBLICATION: publish complete newspaper on preceding day")
    if published >= start:
        errors.append("POST_START: cannot claim pre-race prediction")
    if not race.get("runners") or any(not r.get("name") for r in race["runners"]):
        errors.append("RUNNERS_MISSING")
    if not preliminary:
        errors.append("PRELIMINARY_MISSING")
    if len(discussions) < 5:
        errors.append("DISCUSSION_TOPICS_LT_5")
    if not final:
        errors.append("FINAL_PREDICTION_MISSING")
    for author, record in final.items():
        if record.get("mode") not in ("independent_execution", "single_model_simulation", "editorial"):
            errors.append(f"UNVERIFIED_MODE:{author}")
        if not record.get("saved_at"):
            errors.append(f"UNSAVED_FINAL:{author}")
        else:
            saved = datetime.fromisoformat(record["saved_at"])
            if saved.tzinfo is None or saved >= start:
                errors.append(f"INVALID_FINAL_TIMESTAMP:{author}")
        if record.get("mode") == "independent_execution" and not record.get("execution_id"):
            errors.append(f"INDEPENDENT_EXECUTION_UNPROVEN:{author}")
        if not record.get("picks") and not record.get("skip_reason"):
            errors.append(f"NO_PICKS_OR_SKIP:{author}")
    return {"ready": not errors, "errors": errors, "race_id": race["race_id"]}

def append_revision(history, revision):
    """Append-only update: keep preceding-day version for outcome comparisons."""
    if not history:
        raise ValueError("previous-day version required")
    if any(x["version"] == revision["version"] for x in history):
        raise ValueError("duplicate version")
    if datetime.fromisoformat(revision["saved_at"]) <= datetime.fromisoformat(history[-1]["saved_at"]):
        raise ValueError("revision timestamp must increase")
    return [*history, revision]
