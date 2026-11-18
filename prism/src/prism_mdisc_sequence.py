"""PRISM discussion-before-final gate. Simulation is not independent execution."""
from datetime import datetime
from zoneinfo import ZoneInfo
JST = ZoneInfo("Asia/Tokyo")
MODES = ("independent_execution", "single_model_simulation", "editorial")
TOPICS = ("all_runners", "course_bias", "condition_evidence", "pick_debate", "tickets")
def instant(value):
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() is None: raise ValueError("timezone required")
    return t
def audit(race, preliminary, discussions, finals, paper):
    errors = []
    start = instant(race["start_at"])
    if not race.get("race_id") or not race.get("runners") or any(not r.get("name") for r in race.get("runners", [])):
        errors.append("RACE_INPUT_INCOMPLETE")
    if not preliminary: errors.append("PRE_MISSING")
    if not finals: errors.append("FINAL_MISSING")
    if not paper: errors.append("PAPER_MISSING")
    for topic in TOPICS:
        if topic not in {d.get("topic") for d in discussions}: errors.append("TOPIC_MISSING:"+topic)
    discussion_times = []
    for d in discussions:
        if not d.get("saved_at"): errors.append("DISCUSSION_UNSAVED"); continue
        t = instant(d["saved_at"]); discussion_times.append(t)
        if t >= start: errors.append("DISCUSSION_AFTER_START")
        if not d.get("character_id") or not d.get("character_url"): errors.append("CHARACTER_ATTRIBUTION_MISSING")
        if d.get("mode") not in MODES: errors.append("DISCUSSION_MODE_UNKNOWN")
        if d.get("mode") == "independent_execution" and not d.get("execution_id"): errors.append("DISCUSSION_EXECUTION_UNPROVEN")
    for author, pre in preliminary.items():
        if pre.get("mode") not in MODES: errors.append("PRE_MODE_UNKNOWN:"+author)
        if not pre.get("saved_at"): errors.append("PRE_UNSAVED:"+author); continue
        t = instant(pre["saved_at"])
        if t >= start: errors.append("PRE_AFTER_START:"+author)
        if pre.get("mode") == "independent_execution" and not pre.get("execution_id"): errors.append("PRE_EXECUTION_UNPROVEN:"+author)
        if author not in finals: errors.append("FINAL_MISSING_FOR:"+author)
        if not discussion_times or t >= min(discussion_times):
            errors.append("PRE_NOT_BEFORE_DISCUSSION:"+author)
    for author, final in finals.items():
        if author not in preliminary: errors.append("FINAL_WITHOUT_PRE:"+author)
        if final.get("mode") not in MODES: errors.append("FINAL_MODE_UNKNOWN:"+author)
        if not final.get("saved_at"): errors.append("FINAL_UNSAVED:"+author); continue
        t = instant(final["saved_at"])
        if t >= start: errors.append("FINAL_AFTER_START:"+author)
        if not discussion_times or t <= max(discussion_times): errors.append("FINAL_BEFORE_DISCUSSION_END:"+author)
        if final.get("mode") == "independent_execution" and not final.get("execution_id"): errors.append("FINAL_EXECUTION_UNPROVEN:"+author)
        if not final.get("picks") and not final.get("skip_reason"): errors.append("FINAL_NO_PICKS_OR_SKIP:"+author)
    if paper and not paper.get("published_at"): errors.append("PAPER_UNPUBLISHED")
    if paper and paper.get("published_at"):
        t = instant(paper["published_at"])
        if t.astimezone(JST).date() >= start.astimezone(JST).date(): errors.append("PAPER_NOT_PREVIOUS_DAY")
        if any(t <= instant(f["saved_at"]) for f in finals.values() if f.get("saved_at")): errors.append("PAPER_BEFORE_FINAL")
    return {"ready":not errors, "errors":sorted(set(errors))}
