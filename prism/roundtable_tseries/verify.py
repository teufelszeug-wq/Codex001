"""PRISM roundtable acceptance gate. Usage: python verify.py meeting.json"""
import json,sys
from collections import Counter
def verify(x):
    errors=[]
    race=x.get("race",{})
    horses=x.get("horses",[])
    turns=x.get("turns",[])
    if race.get("expected_count")!=len(horses):errors.append("RUNNER_COUNT_MISMATCH")
    nums=[h.get("number") for h in horses]
    if nums!=list(range(1,len(horses)+1)):errors.append("ROSTER_ORDER_OR_GAP")
    names={h.get("number"):h.get("name") for h in horses}
    if len(set(names.values()))!=len(horses):errors.append("DUPLICATE_HORSE_NAME")
    seen=set();core=Counter();intro=[];stages=[]
    for t in turns:
        tid=t.get("id")
        if tid in seen:errors.append("DUPLICATE_TURN_ID")
        ref=t.get("responds_to")
        if ref is not None and ref not in seen:errors.append("BROKEN_REPLY")
        seen.add(tid)
        s=t.get("stage");stages.append(s);n=t.get("horse")
        if s=="HORSE_INTRO":intro.append(n)
        if s=="HORSE_CORE":core[n]+=1
        if str(s).startswith("HORSE_") and (n not in names or names[n] not in t.get("text","")):
            errors.append("HORSE_NUMBER_AND_NAME_REQUIRED")
        if any(w in t.get("text","") for w in ("上げたい","下げたい","上にしたい")):
            errors.append("INTERNAL_SCORE_JARGON")
    if not stages or stages[0]!="RACE_INTRO":errors.append("INTRO_REQUIRED")
    if "COURSE" not in stages or ("HORSE_INTRO" in stages and stages.index("COURSE")>stages.index("HORSE_INTRO")):
        errors.append("COURSE_BEFORE_HORSES")
    if intro!=nums:errors.append("HORSE_SEQUENCE")
    if any(core[n]!=1 for n in nums):errors.append("HORSE_OMISSION_OR_DUPLICATE")
    if "COMPARE_START" not in stages or "CLOSE" not in stages:errors.append("COMPARE_AND_CLOSE_REQUIRED")
    if x.get("independent_ai_calls",0) and x.get("meeting_mode")=="SINGLE_MODEL_ROLE_SIMULATION":
        errors.append("INDEPENDENCE_MISREPRESENTED")
    return {"status":"PASS" if not errors else "FAIL","errors":sorted(set(errors)),
      "horses":len(horses),"cores":sum(core.values()),"turns":len(turns),
      "speakers":len({t.get("speaker") for t in turns})}
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("Usage: verify.py meeting.json")
    with open(sys.argv[1],encoding="utf-8") as f:result=verify(json.load(f))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result["status"]=="PASS" else 1)
