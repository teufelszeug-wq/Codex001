#!/usr/bin/env python3
"""PRISM immutable pre-off envelope. Reject incomplete/untrusted input; never invent forecasts."""
import argparse, datetime as dt, json, pathlib, re, sys
from urllib.parse import urlparse
JST=dt.timezone(dt.timedelta(hours=9))
SAFE=re.compile(r"^[A-Za-z0-9_-]{1,100}$")
def check(obj,now):
    errors=[]
    if not isinstance(obj,dict): return ["input:not_object"]
    for k in ("race_id","off_at","official_racecard_url","horses","honshi"):
        if not obj.get(k): errors.append("missing:"+k)
    for k in ("race_id","version"):
        val=obj.get(k,"pre-v1" if k=="version" else "")
        if not isinstance(val,str) or not SAFE.fullmatch(val): errors.append("unsafe:"+k)
    url=obj.get("official_racecard_url","")
    if not isinstance(url,str) or urlparse(url).scheme!="https" or not urlparse(url).netloc:
        errors.append("invalid_official_racecard_url")
    try:
        off=dt.datetime.fromisoformat(obj["off_at"])
        if off.tzinfo is None: errors.append("off_at:no_timezone")
        elif now>=off: errors.append("race_already_started")
    except (KeyError,ValueError,TypeError): errors.append("invalid_off_at")
    horses=obj.get("horses")
    if not isinstance(horses,list) or not horses: errors.append("horses:empty_or_invalid"); horses=[]
    if any(not isinstance(h,dict) for h in horses): errors.append("horses:invalid_record"); horses=[h for h in horses if isinstance(h,dict)]
    nums=[h.get("horse_no") for h in horses]
    if len(set(map(str,nums)))!=len(nums): errors.append("duplicate_horse_no")
    if any(type(n) is not int or n<1 for n in nums): errors.append("invalid_horse_no")
    if any(not h.get("horse_name") or not h.get("diagnosis") for h in horses): errors.append("incomplete_full_field_diagnosis")
    h=obj.get("honshi")
    if not isinstance(h,dict): errors.append("honshi:invalid"); h={}
    marks=h.get("marks")
    if not isinstance(marks,dict) or not marks: errors.append("honshi:missing_marks")
    elif any(type(n) is not int or n not in nums for n in marks.values()): errors.append("honshi:unknown_horse_no")
    bets=h.get("bets",[])
    if not isinstance(bets,list): errors.append("honshi:invalid_bets"); bets=[]
    if not bets and not h.get("pass_reason"): errors.append("honshi:missing_bets_or_pass")
    for bet in bets:
        if not isinstance(bet,dict) or type(bet.get("stake_yen")) is not int or bet["stake_yen"]<=0 or bet["stake_yen"]%100:
            errors.append("invalid_100yen_stake")
    return errors
def main():
    p=argparse.ArgumentParser(); p.add_argument("input"); p.add_argument("output_dir"); a=p.parse_args()
    obj=json.loads(pathlib.Path(a.input).read_text(encoding="utf8"))
    now=dt.datetime.now(JST); errors=check(obj,now)
    if errors:
        print(json.dumps({"saved":False,"errors":errors},ensure_ascii=False)); return 1
    # Recheck at the actual write boundary; validation may have taken time.\n    write_now=dt.datetime.now(JST)\n    errors=check(obj,write_now)\n    if errors:\n        print(json.dumps({"saved":False,"errors":errors},ensure_ascii=False)); return 1\n    out=dict(obj,version=obj.get("version","pre-v1"),saved_at=write_now.isoformat(),record_type="pre_off_forecast",forecaster_id="honshi")
    path=pathlib.Path(a.output_dir)/(obj["race_id"]+"__"+out["version"]+".json")
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
    print(json.dumps({"saved":True,"path":str(path),"race_id":obj["race_id"],"saved_at":out["saved_at"]},ensure_ascii=False)); return 0
if __name__=="__main__": sys.exit(main())
