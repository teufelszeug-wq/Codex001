"""Convert a verified racecard and complete independent forecast set to preday envelopes.

Caller must authenticate source and create forecasts; this module does neither.
"""
from datetime import datetime, timezone

def build_preday_records(racecard, forecasts, *, forecaster_id, version, saved_at=None):
    if not isinstance(racecard, dict) or racecard.get("source_authenticity_verified") is not True:
        raise ValueError("authenticated racecard required")
    for key in ("race_id", "source_id", "scheduled_start_at"):
        if not isinstance(racecard.get(key), str) or not racecard[key].strip():
            raise ValueError("missing " + key)
    horses = racecard.get("horses")
    if not isinstance(horses, list) or not horses or not isinstance(forecasts, list) or not forecasts:
        raise ValueError("nonempty horses and forecasts required")
    if not all(isinstance(x, str) and x.strip() for x in (forecaster_id, version)):
        raise ValueError("forecaster_id and version required")
    by_id = {}
    for horse in horses:
        if not isinstance(horse, dict) or not all(isinstance(horse.get(k), str) and horse[k].strip() for k in ("horse_id", "horse_name")):
            raise ValueError("invalid horse identity")
        if horse["horse_id"] in by_id:
            raise ValueError("duplicate racecard horse")
        by_id[horse["horse_id"]] = horse["horse_name"]
    stamp = saved_at or datetime.now(timezone.utc).isoformat()
    seen, records = set(), []
    for forecast in forecasts:
        if not isinstance(forecast, dict) or forecast.get("horse_id") not in by_id:
            raise ValueError("unknown forecast horse")
        hid = forecast["horse_id"]
        if hid in seen:
            raise ValueError("duplicate forecast horse")
        if "prediction" not in forecast or forecast["prediction"] is None:
            raise ValueError("missing prediction for " + hid)
        prediction = forecast["prediction"]
        if isinstance(prediction, bool) or (isinstance(prediction, (dict, list, str)) and not prediction):
            raise ValueError("empty or invalid prediction for " + hid)
        if isinstance(prediction, float):
            from math import isfinite
            if not isfinite(prediction):
                raise ValueError("nonfinite prediction for " + hid)
        # Reject malformed baseline probabilities before any batch write.
        if isinstance(prediction, dict) and "win_probability" in prediction:
            from math import isfinite
            probability = prediction["win_probability"]
            if (isinstance(probability, bool)
                    or not isinstance(probability, (int, float))
                    or not isfinite(probability)
                    or not 0.0 <= probability <= 1.0):
                raise ValueError("invalid win_probability for " + hid)
        seen.add(hid)
        records.append(dict(race_id=racecard["race_id"], horse_id=hid,
            horse_name=by_id[hid], forecaster_id=forecaster_id,
            source_id=racecard["source_id"], saved_at=stamp, version=version,
            scheduled_start_at=racecard["scheduled_start_at"],
            source_authenticity_verified=True, record_type="preday_forecast",
            prediction=forecast.get("prediction")))
    if seen != set(by_id):
        raise ValueError("all runners must be forecast")
    return records
