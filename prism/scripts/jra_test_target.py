"""Guard PRISM race tests against fabricated JRA fixtures.

The operator must supply an official racecard URL for a scheduled JRA race.
A requested calendar date alone never creates a race.
"""
from datetime import date

def select_test_target(requested_date: date, official_events: list[dict]) -> dict:
    matches = [
        event for event in official_events
        if event.get("date") == requested_date.isoformat()
        and event.get("organizer") == "JRA"
        and event.get("grade") in {"G1", "G2", "G3", "JG1", "JG2", "JG3"}
        and event.get("official_racecard_url")
    ]
    if not matches:
        return {
            "state": "NO_OFFICIAL_GRADED_RACE",
            "date": requested_date.isoformat(),
            "selected": None,
            "reason": "No verified official JRA graded racecard for requested date; do not fabricate runners.",
        }
    return {"state": "READY", "date": requested_date.isoformat(), "selected": matches[0]}
