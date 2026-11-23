"""Validate video evidence before PRISM forecasts consume it.

Pure validation: no video playback or external claims. Preserve unknown publication
times as null; post-race observations cannot become pre-race evidence.
"""
from datetime import datetime
from math import isfinite
from urllib.parse import urlparse

STATES = {"page_only", "partial_playback", "full_playback", "unpublished", "unplayable"}
REQUIRED = ("evidence_id", "race_id", "horse_name", "target_date", "publisher",
            "url", "published_at", "checked_at", "check_method", "checked_by",
            "video_start", "video_end", "status", "observations", "article_claims",
            "interpretation", "changed_forecast")

def instant(value):
    if value is None:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must have timezone")
    return dt

def validate(item, *, forecast_saved_at=None, off_at=None, phase="pre_race"):
    if not isinstance(item, dict):
        raise ValueError("evidence must be object")
    absent = [key for key in REQUIRED if key not in item]
    if absent:
        raise ValueError("missing evidence fields: " + ", ".join(absent))
    if item["status"] not in STATES:
        raise ValueError("invalid verification status")
    if not all(isinstance(item[k], str) and item[k].strip() for k in
               ("evidence_id", "race_id", "horse_name", "target_date", "publisher", "url",
                "check_method", "checked_by")):
        raise ValueError("required text blank")
    if urlparse(item["url"]).scheme not in ("https", "http"):
        raise ValueError("invalid video URL")
    if not isinstance(item["changed_forecast"], bool):
        raise ValueError("changed_forecast must be boolean")
    checked = instant(item["checked_at"])
    published = instant(item["published_at"])
    if checked is None:
        raise ValueError("checked_at required")
    if published and published > checked:
        raise ValueError("publication after check")
    start, end = item["video_start"], item["video_end"]
    played = item["status"] in ("partial_playback", "full_playback")
    if played and (not isinstance(start, (int, float)) or isinstance(start, bool) or
                   not isinstance(end, (int, float)) or isinstance(end, bool) or
                   not isfinite(start) or not isfinite(end) or
                   start < 0 or end <= start):
        raise ValueError("playback requires valid timestamp range")
    if not played and (start is not None or end is not None):
        raise ValueError("unplayed evidence cannot claim video time range")
    if item["status"] in ("unpublished", "unplayable", "page_only") and item["changed_forecast"]:
        raise ValueError("unverified playback cannot directly change forecast")
    if phase == "pre_race":
        saved, off = instant(forecast_saved_at), instant(off_at)
        if saved is None or off is None or saved >= off:
            raise ValueError("pre-race forecast times invalid")
        if checked > saved or (published is not None and published > saved):
            raise ValueError("future video evidence leaked into forecast")
    elif phase != "review":
        raise ValueError("invalid phase")
    return True
