#!/usr/bin/env python3
"""PRISM: create immutable pre-off forecast envelope from verified inputs.
No forecast is fabricated. Exits nonzero on missing required evidence.
"""
import argparse, datetime as dt, json, pathlib, sys
JST=dt.timezone(dt.timedelta(hours=9))
def check(obj, now):
    problems=[]
    for k in ("race_id","off_at","official_racecard_url","horses","honshi"):
        if not obj.get(k): problems.append("missing:"+k)
    try:
        off=dt.datetime.fromisoformat(obj["off_at"])
        if off.tzinfo is None: problems.append("off_at:no_timezone")
        elif now>=off: problems.append("race_already_started")
    except (KeyError,ValueError,TypeError): problems.append("invalid_off_at")
    horses=obj.get("horses",[])
    if len({h.get("horse_no") for h in horses})!=len(horses): problems.append("duplicate_horse_no")
    if any(not h.get("horse_name") or not h.get("diagnosis") for h in horses): problems.append("incomplete_full_field_diagnosis")
    h=obj.get("honshi",{})
    if not h.get("marks"): problems.append("honshi:missing_marks")
    if not h.get("bets") and not h.get("pass_reason"): problems.append("honshi:missing_bets_or_pass")
    for bet in h.get("bets",[]):
        if not isinstance(bet.get("stake_yen"),int) or bet["stake_yen"]<=0 or bet["stake_yen"]%100: problems.append("invalid_100yen_stake")
    return problems
def main():
    p=argparse.ArgumentParser();p.add_argument("input");p.add_argument("output_dir");a=p.parse_args()
    obj=json.loads(pathlib.Path(a.input).read_text(encoding="utf8"))
    now=dt.datetime.now(JST);errors=check(obj,now)
    if errors:
        print(json.dumps({"saved":False,"errors":errors},ensure_ascii=False));return 1
    out=dict(obj,version=obj.get("version","pre-v1"),saved_at=now.isoformat(),record_type="pre_off_forecast",forecaster_id="honshi")
    path=pathlib.Path(a.output_dir)/(str(obj["race_id"])+"__"+out["version"]+".json")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf8") as f:json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps({"saved":True,"path":str(path),"race_id":obj["race_id"],"saved_at":out["saved_at"]},ensure_ascii=False));return 0
if __name__=="__main__":sys.exit(main())
