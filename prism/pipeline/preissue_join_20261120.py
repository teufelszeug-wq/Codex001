"""PRISM strict source-to-paper preissue join; no invented forecasts."""
from datetime import datetime
MARKS = ('◎','○','▲','△','☆')
def build_preissue(race, entries, predictions, characters):
    start = datetime.fromisoformat(race['start_at'])
    horses = {e['horse_number']:e for e in entries}
    errors = []
    if not entries or len(horses)!=len(entries) or any(not e.get('horse_name') or not isinstance(e.get('frame_number'),int) for e in entries):
        errors.append('OFFICIAL_ENTRIES_INCOMPLETE')
    accepted=[]
    for p in predictions:
        reasons=[]
        if p.get('race_id')!=race['race_id']: reasons.append('RACE_ID_MISMATCH')
        if p.get('status')!='FORMAL_PRE' or p.get('execution_type')=='EDITORIAL_SINGLE_MODEL': reasons.append('NOT_FORMAL_PRE')
        try:
            if datetime.fromisoformat(p['saved_at'])>=start: reasons.append('LATE_SAVE')
        except (KeyError,ValueError,TypeError): reasons.append('INVALID_SAVED_AT')
        c=characters.get(p.get('character_id'))
        if not c or not all(c.get(k) for k in ('url','role','verified_at')): reasons.append('CHARACTER_UNVERIFIED')
        if not p.get('source_url') or not p.get('version'): reasons.append('SOURCE_UNVERIFIED')
        marks=p.get('marks',{})
        if any(k not in marks for k in MARKS): reasons.append('MARKS_INCOMPLETE')
        if any(n not in horses for n in marks.values()): reasons.append('HORSE_MISMATCH')
        if len(set(marks.values()))!=len(marks): reasons.append('DUPLICATE_MARKS')
        bets=p.get('bets',[])
        if not bets or any(not isinstance(b.get('yen'),int) or b['yen']<=0 or b['yen']%100 for b in bets): reasons.append('INVALID_100YEN_BETS')
        if reasons: errors.append({'prediction_id':p.get('prediction_id'),'reasons':reasons})
        else: accepted.append(p)
    return {'race_id':race['race_id'],'status':'HOLD' if errors or not accepted else 'PREISSUE_READY','accepted':accepted,'errors':errors,'missing_predictions':not bool(accepted)}
