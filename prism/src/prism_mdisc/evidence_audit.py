"""Race-level, evidence-linked structural checks. No semantic-quality claim."""
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from .core import audit_session, text_fingerprint, EvidenceType

REQUIRED_TOPICS = ('all_horses','course_bias','condition_information','main_pick_comparison','tickets')

def timestamp(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError('timezone required')
    return dt.astimezone(timezone.utc)

@dataclass(frozen=True)
class Evidence:
    ref: str
    source: str
    text: str
    content_sha256: str
    published_at: str
    available_at: str
    kind: str = 'observed'

    def validate(self,cutoff):
        if not self.ref or not self.source or not self.text.strip(): raise ValueError('empty evidence')
        if self.kind not in ('observed','computed','synthetic'): raise ValueError('invalid evidence kind')
        if sha256(self.text.encode()).hexdigest()!=self.content_sha256: raise ValueError('evidence hash mismatch')
        if not timestamp(self.published_at)<=timestamp(self.available_at)<=timestamp(cutoff): raise ValueError('future evidence')

def audit_race(race_id, horse_ids, ai_ids, sessions, topic_by_session, evidence, cutoff, judgments, invalidated_ids=()):
    """Judgments require each AI's initial view, response to another, and final view.

    Evidence timestamps/source authenticity remain caller-supplied. Passing this
    function does not establish human acceptance or predictive improvement.
    """
    timestamp(cutoff)
    errors=[]; ids=set(); bodies=set(); valid=[]; accepted_chars=0
    if not horse_ids or len(set(horse_ids))!=len(horse_ids): errors.append('invalid_horse_roster')
    if len(ai_ids)<2 or len(set(ai_ids))!=len(ai_ids): errors.append('invalid_ai_roster')
    evidence_map={}
    for e in evidence:
        if e.ref in evidence_map: errors.append('duplicate_evidence_ref'); continue
        try: e.validate(cutoff)
        except (ValueError,TypeError): errors.append('invalid_evidence:'+e.ref); continue
        evidence_map[e.ref]=e
    for s in sessions:
        if s.session_id in invalidated_ids:continue
        start=len(errors); fp=text_fingerprint(s)
        if s.session_id in ids or fp in bodies:
            errors.append('duplicate_session:'+s.session_id);continue
        ids.add(s.session_id);bodies.add(fp)
        if s.race.race_id!=race_id:errors.append('wrong_race:'+s.session_id)
        report=audit_session(s)
        if not report.quality_pass:errors.append('session_quality:'+s.session_id)
        if any(p not in ai_ids for p in s.participants):errors.append('unknown_ai:'+s.session_id)
        if s.session_id not in topic_by_session:errors.append('missing_topic:'+s.session_id)
        for t in s.turns:
            if t.evidence_ref and t.evidence_ref not in evidence_map:errors.append('unresolved_evidence:'+t.evidence_ref)
        if len(errors)==start:
            valid.append(s);accepted_chars+=report.chars
    topics={topic_by_session[s.session_id] for s in valid}
    missing_topics=sorted(set(REQUIRED_TOPICS)-topics)
    if missing_topics:errors.append('missing_required_topics')
    index={s.session_id:s for s in valid}
    coverage=set()
    for j in judgments:
        key=(j['horse_id'],j['ai_id'])
        if key in coverage:errors.append('duplicate_judgment');continue
        if key[0] not in horse_ids or key[1] not in ai_ids:errors.append('unknown_judgment_subject');continue
        ok=True
        for phase in ('initial','response','final'):
            link=j[phase]; s=index.get(link['session_id']);i=link['turn_index']
            if s is None or type(i) is not int or not 0<=i<len(s.turns) or s.turns[i].speaker!=key[1] or key[0] not in s.turns[i].horse_ids:ok=False;break
        if not ok:errors.append('invalid_judgment_links');continue
        # Cross-session chronology must be supplied in session order.
        order={s.session_id:i for i,s in enumerate(valid)}
        links=[(order[j[p]['session_id']],j[p]['turn_index']) for p in ('initial','response','final')]
        if not links[0]<links[1]<links[2]:errors.append('invalid_judgment_order');continue
        response=j['response']; target=response.get('responds_to');s=index[response['session_id']]
        if type(target) is not int or not 0<=target<response['turn_index'] or s.turns[target].speaker==key[1]:
            errors.append('invalid_response_target');continue
        coverage.add(key)
    expected={(h,a) for h in horse_ids for a in ai_ids}
    missing=sorted(expected-coverage)
    if missing:errors.append('missing_ai_horse_judgments')
    return {'status':'STRUCTURAL_PASS' if not errors else 'FAIL', 'race_id':race_id,
            'valid_sessions':len(valid),'valid_chars':accepted_chars,'missing_topics':missing_topics,
            'judgment_coverage':{'complete':len(coverage),'expected':len(expected),'missing':missing},
            'errors':errors,'excluded_invalidated_ids':sorted(set(invalidated_ids)),
            'semantic_review_required':True,'training_achievement_verified':False,
            'note':'Counts are structural evidence only; semantic independence and source authenticity require review.'}
