"""Connect saved forecasts to sourced official 100-yen payouts (no network retrieval)."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from settlement_100yen import settle
from forecast_preflight import validate as validate_forecast

def settle_release(forecast_path, official_path):
    raw = Path(forecast_path).read_bytes()
    doc = json.loads(raw)
    result = json.loads(Path(official_path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(result, dict):
        raise ValueError("documents must be objects")
    preflight_errors = validate_forecast(doc)
    if preflight_errors:
        raise ValueError("forecast preflight failed: " + ",".join(preflight_errors))
    race = doc.get("race_id")
    if not isinstance(race, str) or not race.strip() or race != result.get("race_id"):
        raise ValueError("race_id mismatch")
    if type(doc.get("version")) is not int or doc["version"] < 1:
        raise ValueError("invalid version")
    try:
        saved, off = (datetime.fromisoformat(doc[k]) for k in ("saved_at", "off_at"))
        if any(t.tzinfo is None or t.utcoffset() is None for t in (saved, off)) or saved >= off:
            raise ValueError("not a pre-off forecast")
    except (KeyError, TypeError) as exc:
        raise ValueError("invalid forecast time") from exc
    if result.get("status") != "official":
        raise ValueError("unverified result status")
    url = result.get("source_url")
    if not isinstance(url, str) or not url.startswith(("https://", "http://")):
        raise ValueError("official source URL required")
    if not isinstance(result.get("payouts"), list):
        raise ValueError("payouts must be list")
    payouts = {}
    for row in result["payouts"]:
        if not isinstance(row, dict):
            raise ValueError("invalid payout row")
        kind, selection, amount = (row.get(k) for k in ("bet_type", "selection", "payout_yen_per_100"))
        if not isinstance(kind, str) or not kind.strip() or not isinstance(selection, str) or not selection.strip() or type(amount) is not int or amount < 0:
            raise ValueError("invalid payout fields")
        key = (kind.strip(), selection.strip())
        if key in payouts:
            raise ValueError("duplicate payout key")
        payouts[key] = amount
    records = doc.get("records")
    if not isinstance(records, list) or not records:
        raise ValueError("missing forecasters")
    seen, outputs = set(), []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("invalid record")
        fid = record.get("forecaster_id")
        if not isinstance(fid, str) or not fid.strip() or fid.strip() in seen:
            raise ValueError("missing or duplicate forecaster_id")
        fid = fid.strip()
        seen.add(fid)
        if record.get("decision") == "abstain":
            if record.get("bets"):
                raise ValueError("abstain cannot contain bets")
            bets = []
        elif record.get("decision") == "bet":
            bets = record.get("bets")
            if not isinstance(bets, list) or not bets:
                raise ValueError("bet decision requires bets")
            for bet in bets:
                if not isinstance(bet, dict) or not isinstance(bet.get("horse_name"), str) or not bet["horse_name"].strip():
                    raise ValueError("horse_name required")
                if not isinstance(bet.get("bet_type"), str) or not bet["bet_type"].strip() or not isinstance(bet.get("selection"), str) or not bet["selection"].strip():
                    raise ValueError("bet_type and selection required")
        else:
            raise ValueError("invalid decision")
        outputs.append({"forecaster_id": fid, **settle(bets, payouts)})
    return {"race_id": race, "version": doc["version"], "saved_at": doc["saved_at"],
            "forecast_sha256": hashlib.sha256(raw).hexdigest(),
            "result_source_url": url, "result_status": "official", "forecasters": outputs}

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        raise SystemExit("usage: settle_release.py FORECAST.json OFFICIAL.json")
    print(json.dumps(settle_release(sys.argv[1], sys.argv[2]), ensure_ascii=False, indent=2))
