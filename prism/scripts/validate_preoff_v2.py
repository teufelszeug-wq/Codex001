#!/usr/bin/env python3
"""Strict production pre-off gate. No synthetic or retrospective credit."""
import json,sys
from datetime import datetime

def dt(s):
    d=datetime.fromisoformat(s)
    if d.tzinfo is None or d.utcoffset() is None: raise ValueError("timezone_required")
    return d

def validate(r):
    errors=[]
    rid=r.get("race_id","UNKNOWN")
    try: off=dt(r["off_at"])
    except (KeyError,TypeError,ValueError): return {"race_id":rid,"accepted":False,"errors":["invalid_off_at"]}
    if not r.get("official_racecard_url"): errors.append("official_racecard_missing")
    if not r.get("full_field_diagnosis_verified"): errors.append("full_field_unverified")
    forecasts=r.get("forecasts") or []
    ids=set()
    for f in forecasts:
        who=f.get("forecaster_id","unknown")
        if who in ids: errors.append(who+":duplicate_forecaster")
        ids.add(who)
        if not f.get("run_id") or not f.get("source_url") or not f.get("version"): errors.append(who+":missing_provenance")
        try:
            if dt(f["saved_at"])>=off: errors.append(who+":not_pre_off")
        except (KeyError,TypeError,ValueError): errors.append(who+":invalid_saved_at")
        if f.get("execution_mode") in ("single_model_role_text","roleplay","synthetic") or f.get("kind")=="roleplay": errors.append(who+":not_independent")
        if who!="honshi" and f.get("execution_mode")!="independent": errors.append(who+":independent_execution_unverified")
        bets=f.get("bets_100yen")
        if bets is None:
            if not f.get("pass_reason"): errors.append(who+":missing_bet_or_pass")
        elif not isinstance(bets,list) or not bets: errors.append(who+":invalid_bets")
        else:
            for b in bets:
                stake=b.get("stake_yen") if isinstance(b,dict) else None
                if type(stake) is not int or stake<=0 or stake%100: errors.append(who+":invalid_stake")
    for who in ("honshi","rio"):
        if who not in ids: errors.append("missing_"+who)
    for key in ("five_topic_roundtable_verified","vertical_newspaper_verified","official_settlement_verified"):
        if not r.get(key): errors.append(key+":unverified")
    return {"race_id":rid,"accepted":not errors,"errors":errors}

def main(path):
    with open(path,encoding="utf8") as fh: data=json.load(fh)
    results=[validate(r) for r in data.get("targets",data.get("races",[]))]
    print(json.dumps({"total":len(results),"accepted":sum(r["accepted"] for r in results),"results":results},ensure_ascii=False,indent=2))
    return 0 if results and all(r["accepted"] for r in results) else 1
if __name__=="__main__": sys.exit(main(sys.argv[1]) if len(sys.argv)==2 else 2)
