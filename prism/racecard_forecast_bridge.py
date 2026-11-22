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
    # The persistence contract requires a real source retrieval timestamp.
    # Reject incomplete provenance before constructing forecast records.
    if not isinstance(racecard.get("source_retrieved_at"), str) or not racecard["source_retrieved_at"].strip():
        raise ValueError("missing source_retrieved_at")
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
    def parse_aware(value, label):
        if not isinstance(value, str):
            raise ValueError(label + " must be an ISO timestamp")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("invalid " + label) from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError(label + " must include timezone")
        return parsed.astimezone(timezone.utc)

    stamp = saved_at if saved_at is not None else datetime.now(timezone.utc).isoformat()
    saved_time = parse_aware(stamp, "saved_at")
    start_time = parse_aware(racecard["scheduled_start_at"], "scheduled_start_at")
    if saved_time >= start_time:
        raise ValueError("preday forecast must be saved before scheduled start")
    # A preday edition must be committed on a calendar day preceding race day
    # in Japan, not merely minutes before the scheduled start.
    from datetime import timedelta
    jst = timezone(timedelta(hours=9))
    if saved_time.astimezone(jst).date() >= start_time.astimezone(jst).date():
        raise ValueError("preday forecast must be saved before race day in JST")
    if saved_time > datetime.now(timezone.utc):
        raise ValueError("saved_at cannot be in the future")
    if "source_retrieved_at" in racecard:
        retrieved_time = parse_aware(racecard["source_retrieved_at"], "source_retrieved_at")
        if retrieved_time > saved_time:
            raise ValueError("source retrieved after forecast saved_at")
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
        if not isinstance(prediction, dict) or not prediction:
            raise ValueError("empty or invalid prediction for " + hid)
        if "win_probability" not in prediction:
            raise ValueError("missing win_probability for " + hid)
        # Reject malformed baseline probabilities before any batch write.
        if "win_probability" in prediction:
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
            prediction=forecast.get("prediction"),
            **({"source_retrieved_at": racecard["source_retrieved_at"]}
               if "source_retrieved_at" in racecard else {})))
    if seen != set(by_id):
        raise ValueError("all runners must be forecast")
    # A full-field win market must be coherent, not just individually bounded.
    probability_flags = [isinstance(r['prediction'], dict) and 'win_probability' in r['prediction'] for r in records]
    if any(probability_flags):
        if not all(probability_flags):
            raise ValueError('partial win_probability coverage')
        from math import fsum, isclose
        total = fsum(float(r['prediction']['win_probability']) for r in records)
        if not isclose(total, 1.0, rel_tol=0.0, abs_tol=1e-8):
            raise ValueError('win_probability sum must equal 1')
    return records
