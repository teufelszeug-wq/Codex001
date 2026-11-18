#!/usr/bin/env python3
"""PRISM production acceptance gate. Does not infer evidence from a role-play or CI."""
import json, sys
from datetime import datetime

REQUIRED = ("race_id", "off_at", "source_url", "forecasts")
def timestamp(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("timestamp must contain timezone offset")
    return dt

def audit(race):
    errors = []
    for key in REQUIRED:
        if not race.get(key):
            errors.append("missing:"+key)
    if errors: return {"race_id":race.get("race_id"),"accepted":False,"errors":errors}
    try: off = timestamp(race["off_at"])
    except (ValueError,TypeError) as e:
        return {"race_id":race["race_id"],"accepted":False,"errors":["off_at:"+str(e)]}
    if not race.get("official_racecard_verified"): errors.append("official_racecard_unverified")
    if not race.get("full_field_diagnosis_verified"): errors.append("full_field_diagnosis_unverified")
    for f in race["forecasts"]:
        who=f.get("forecaster_id","unknown")
        if not f.get("run_id"): errors.append(who+":missing_run_id")
        if not f.get("version"): errors.append(who+":missing_version")
        if not f.get("source_url"): errors.append(who+":missing_source_url")
        if not f.get("saved_at"): errors.append(who+":missing_saved_at")
        else:
            try:
                if timestamp(f["saved_at"]) >= off: errors.append(who+":not_pre_off")
            except (ValueError,TypeError): errors.append(who+":invalid_saved_at")
        if f.get("kind")=="roleplay" or f.get("execution_mode")=="single_model_role_text":
            errors.append(who+":not_independent")
        if not f.get("bets_100yen") and not f.get("pass_reason"):
            errors.append(who+":missing_bet_or_pass")
    if not any(f.get("forecaster_id")=="honshi" for f in race["forecasts"]):
        errors.append("missing_honshi")
    if not any(f.get("forecaster_id")=="rio" for f in race["forecasts"]):
        errors.append("missing_rio")
    if not race.get("five_topic_roundtable_verified"): errors.append("roundtable_unverified")
    if not race.get("vertical_newspaper_verified"): errors.append("newspaper_unverified")
    if not race.get("official_settlement_verified"): errors.append("settlement_unverified")
    return {"race_id":race["race_id"],"accepted":not errors,"errors":errors}

if __name__=="__main__":
    if len(sys.argv)!=2:
        print("usage: production_gate.py manifest.json",file=sys.stderr);sys.exit(2)
    with open(sys.argv[1],encoding="utf-8") as f: data=json.load(f)
    races=data.get("targets",data.get("races",[]))
    results=[audit(r) for r in races]
    print(json.dumps({"total":len(results),"accepted":sum(x["accepted"] for x in results),"results":results},ensure_ascii=False,indent=2))
    sys.exit(0 if results and all(x["accepted"] for x in results) else 1)
