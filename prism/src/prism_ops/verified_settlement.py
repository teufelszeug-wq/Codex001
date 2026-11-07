"""Verified-only settlement boundary for PRISM. No unverified PRE enters Forward ROI."""
from prism_ops.race_queue import snapshot_gate
from prism_ops.forecast_completion_gate import settle_forecast, timestamp

def settle_verified_pre(forecast, receipt, official_result, audit_at):
    gate = snapshot_gate(forecast, receipt, audit_at)
    if not gate["verified_pre"]:
        return {"status": "PRE_LOCK_FAILED", "race_id": forecast.get("race_id"),
                "errors": gate["errors"], "by_agent": None}
    if not official_result or not official_result.get("official_source"):
        return {"status": "RESULT_PENDING", "race_id": forecast.get("race_id"),
                "by_agent": None}
    try:
        observed = timestamp(official_result["retrieved_at"])
        off = timestamp(forecast["scheduled_off"])
        audit = timestamp(audit_at)
        if observed < off or observed > audit:
            return {"status": "INVALID_RESULT_TIME", "race_id": forecast.get("race_id"),
                    "by_agent": None}
    except (KeyError, ValueError, TypeError):
        return {"status": "INVALID_RESULT_TIME", "race_id": forecast.get("race_id"),
                "by_agent": None}
    try:
        settled = settle_forecast(forecast, official_result)
    except (KeyError, ValueError, TypeError) as exc:
        return {"status": "SETTLEMENT_INCOMPLETE", "race_id": forecast.get("race_id"),
                "errors": [str(exc)], "by_agent": None}
    return {"status": "SETTLED", **settled, "receipt_location": receipt["immutable_location"]}
