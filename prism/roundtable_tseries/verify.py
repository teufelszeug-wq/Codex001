"""PRISM M-T: strict, stdlib-only machine QA for roundtable transcripts.
Does not judge human conversational quality or authenticate external source timestamps.
Usage: python verify.py path/to/meeting.json
"""
import json,re,sys
from collections import Counter

BAN=('上げたい','下げたい','上にしたい','順位を上げる')
FIELD=('venue','race_no','class','surface','distance_m','start_jst','expected_count','source_url')

def verify(doc):
    race=doc.get('race') or {}; horses=doc.get('horses') or []; turns=doc.get('turns') or []
    errors=[]
    for f in FIELD:
        if race.get(f) in (None,''):errors.append('RACE_FIELD_MISSING:'+f)
    nums=[h.get('number') for h in horses]
    if race.get('expected_count')!=len(horses):errors.append('RUNNER_COUNT_MISMATCH')
    if nums!=list(range(1,len(horses)+1)):errors.append('HORSE_NUMBER_ORDER')
    names={h.get('number'):h.get('name') for h in horses}
    if any(not h.get('name') for h in horses) or len(set(names.values()))!=len(horses):
        errors.append('RUNNER_NAME_INVALID')
    official=doc.get('official_name_map')
    if official is not None and any(official.get(str(n))!=names.get(n) for n in nums):
        errors.append('OFFICIAL_ROSTER_MISMATCH')
    for h in horses:
        if not h.get('evidence') or not h.get('past_fact'):errors.append('HORSE_SOURCE_MISSING')
        if not isinstance(h.get('frame'),int) or not (1<=h.get('frame',0)<=8):
            errors.append('INVALID_FRAME')
    seen=set();cores=Counter();intros=[];stages=[];speakers=set();
    for t in turns:
        tid=t.get('id');stage=t.get('stage');n=t.get('horse');txt=t.get('text','')
        if not isinstance(tid,int) or tid in seen:errors.append('TURN_ID_DUPLICATE_OR_INVALID')
        ref=t.get('responds_to')
        if ref is not None and ref not in seen:errors.append('BROKEN_REPLY_REFERENCE')
        seen.add(tid);stages.append(stage);speakers.add(t.get('speaker'))
        if not txt.strip():errors.append('EMPTY_TURN')
        if any(x in txt for x in BAN):errors.append('UNNATURAL_INTERNAL_RANK_JARGON')
        if stage=='HORSE_INTRO':intros.append(n)
        if stage=='HORSE_CORE':cores[n]+=1
        if isinstance(stage,str) and stage.startswith('HORSE_'):
            if n not in names or names[n] not in txt:errors.append('HORSE_NAME_MISSING')
        for m in re.finditer(r'(?<!\d)(\d{1,2})番',txt):
            k=int(m.group(1))
            if txt[m.end():].startswith(('手','人気','目','枠')):continue
            if k in names and not txt[m.end():].startswith(names[k]):
                errors.append('HORSE_NUMBER_WITHOUT_NAME')
    if not turns or stages[0]!='RACE_INTRO':errors.append('RACE_OPENING_REQUIRED')
    if 'HORSE_INTRO' not in stages or 'COURSE' not in stages or stages.index('COURSE')>stages.index('HORSE_INTRO'):
        errors.append('COURSE_REQUIRED_BEFORE_FIELD')
    if intros!=nums:errors.append('HORSE_ORDER_OR_OMISSION')
    if any(cores.get(n)!=1 for n in nums):errors.append('HORSE_CORE_NOT_EXACTLY_ONCE')
    if 'COMPARE_START' not in stages or 'CLOSE' not in stages:
        errors.append('COMPARISON_CLOSE_REQUIRED')
    elif 'HORSE_INTRO' in stages and not (stages.index('COMPARE_START')>stages.index('HORSE_INTRO') and stages.index('CLOSE')>stages.index('COMPARE_START')):
        errors.append('INVALID_CLOSING_ORDER')
    if not any(t.get('speaker')=='りお' and '？' in t.get('text','') for t in turns):
        errors.append('REPORTER_HAS_NO_QUESTION')
    if not any(t.get('event_type')=='COUNTERARGUMENT' for t in turns):
        errors.append('EXPERT_HAS_NO_COUNTERARGUMENT')
    if doc.get('meeting_mode')=='SINGLE_MODEL_ROLE_SIMULATION' and doc.get('independent_ai_calls',0):
        errors.append('FALSE_INDEPENDENT_AI_CLAIM')
    errors=sorted(set(errors))
    return {'status':'PASS' if not errors else 'FAIL','errors':errors,'horses':len(horses),
            'horses_with_core':sum(cores.get(n)==1 for n in nums),'turns':len(turns),
            'speakers':len(speakers),'audit_only':'MACHINE_STRUCTURE_NOT_HUMAN_NATURALNESS',
            'human_review':'UNVERIFIED','official_source_timestamp':'NOT_AUTHENTICATED'}

if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: python verify.py meeting.json')
    with open(sys.argv[1],encoding='utf-8') as f:r=verify(json.load(f))
    print(json.dumps(r,ensure_ascii=False,indent=2))
    raise SystemExit(0 if r['status']=='PASS' else 1)
