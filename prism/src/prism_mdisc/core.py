from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from hashlib import sha256
from pathlib import Path
from typing import List, Dict, Optional
import json, re
import unicodedata

class EvidenceType(str, Enum):
    FACT='FACT'; DATA='DATA'; VIDEO='VIDEO'; MARKET='MARKET'; HYPOTHESIS='HYPOTHESIS'; COUNTERFACTUAL='COUNTERFACTUAL'

class Move(str, Enum):
    QUESTION='QUESTION'; CLAIM='CLAIM'; CHALLENGE='CHALLENGE'; EVIDENCE='EVIDENCE'; COUNTER_EVIDENCE='COUNTER_EVIDENCE'; REBUTTAL='REBUTTAL'; REEVALUATION='REEVALUATION'; MINORITY='MINORITY'; RIO_SUMMARY='RIO_SUMMARY'

@dataclass(frozen=True)
class RaceContext:
    race_id: str; race_name: str; venue: str; distance_m: int; conditions: str; topic: str

@dataclass
class Turn:
    speaker: str; role: str; move: Move; text: str
    horse_first_mentions: List[str] = field(default_factory=list)
    evidence_type: Optional[EvidenceType] = None
    evidence_ref: Optional[str] = None
    position_before: Optional[str] = None
    position_after: Optional[str] = None
    horse_ids: List[str] = field(default_factory=list)

@dataclass
class Session:
    session_id: str; race: RaceContext; participants: List[str]; turns: List[Turn] = field(default_factory=list)

@dataclass
class Audit:
    chars:int; turns:int; topics:int; challenges:int; rebuttals:int; reevaluations:int; minority:int
    evidence_turns:int; speaker_ratio:Dict[str,float]; chain_count:int; chain_complete:int; quality_pass:bool; reasons:List[str]

REQUIRED_CHAIN={Move.QUESTION,Move.CLAIM,Move.CHALLENGE,Move.EVIDENCE,Move.REBUTTAL,Move.REEVALUATION,Move.RIO_SUMMARY}
HORSE_RE=re.compile(r'(?<!\d)(\d{1,2})\s*[^\s、。]+')

def text_fingerprint(s:Session)->str:
    # Ignore IDs, topic labels, whitespace and width differences when detecting copies.
    text=''.join(t.text for t in s.turns)
    canonical=''.join(unicodedata.normalize('NFKC',text).split())
    return sha256(canonical.encode()).hexdigest()

def audit_session(s:Session)->Audit:
    chars=sum(len(t.text) for t in s.turns)
    counts={p:0 for p in s.participants}
    for t in s.turns: counts[t.speaker]=counts.get(t.speaker,0)+1
    total=max(1,len(s.turns)); ratios={k:v/total for k,v in counts.items()}
    moves=[t.move for t in s.turns]
    # A chain closes at each RIO_SUMMARY; assess moves since prior close.
    chain_count=0; complete=0; bucket=[]
    for m in moves:
        bucket.append(m)
        if m==Move.RIO_SUMMARY:
            chain_count+=1
            if REQUIRED_CHAIN.issubset(set(bucket)): complete+=1
            bucket=[]
    reasons=[]
    if len(set(s.participants))<2 or len(set(s.participants))!=len(s.participants): reasons.append('invalid_participants')
    if any(t.speaker not in s.participants for t in s.turns): reasons.append('unregistered_speaker')
    if set(s.participants)-{t.speaker for t in s.turns}: reasons.append('silent_participant')
    if not s.turns or any(not t.text.strip() for t in s.turns): reasons.append('empty_text')
    if any(t.move in (Move.EVIDENCE,Move.COUNTER_EVIDENCE) and (t.evidence_type is None or not t.evidence_ref) for t in s.turns): reasons.append('missing_evidence_reference')
    if any(t.evidence_type in (EvidenceType.FACT,EvidenceType.DATA,EvidenceType.VIDEO,EvidenceType.MARKET) and not t.evidence_ref for t in s.turns): reasons.append('untraceable_fact')
    if bucket: reasons.append('unfinished_dialogue_chain')
    if any(r>0.50 for k,r in ratios.items() if k!='りお'): reasons.append('speaker_dominance')
    if chain_count==0 or complete/chain_count<0.80: reasons.append('dialogue_chain_incomplete')
    evidence_turns=sum(1 for t in s.turns if t.evidence_type is not None)
    if len(s.turns)>=10 and evidence_turns/len(s.turns)<0.20: reasons.append('low_evidence_density')
    return Audit(chars,total,1,moves.count(Move.CHALLENGE),moves.count(Move.REBUTTAL),moves.count(Move.REEVALUATION),moves.count(Move.MINORITY),evidence_turns,ratios,chain_count,complete,not reasons,reasons)

class DiscussionArchive:
    def __init__(self, root:Path): self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
    def save_session(self,s:Session):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',s.session_id): raise ValueError('unsafe session_id')
        p=self.root/f'{s.session_id}.json'
        raw=json.dumps(asdict(s),ensure_ascii=False,indent=2,default=lambda o:o.value if isinstance(o,Enum) else str(o))
        if p.exists():
            if p.read_text(encoding='utf-8')!=raw: raise ValueError('session is immutable; use a revision ID')
        else:
            with p.open('x',encoding='utf-8') as f: f.write(raw)
        return {'path':str(p),'sha256':sha256(raw.encode()).hexdigest(),'chars':sum(len(t.text) for t in s.turns)}

@dataclass
class DailyGate:
    min_chars:int=100_000; min_complete_chain_ratio:float=.80; min_evidence_density:float=.20
    def evaluate(self,sessions:List[Session])->dict:
        unique=[]; seen_ids=set(); seen_text=set(); duplicates=0
        for s in sessions:
            fingerprint=text_fingerprint(s)
            if s.session_id in seen_ids or fingerprint in seen_text:
                duplicates+=1
                continue
            seen_ids.add(s.session_id); seen_text.add(fingerprint); unique.append(s)
        sessions=unique
        audits=[audit_session(s) for s in sessions]
        chars=sum(a.chars for a in audits); turns=sum(a.turns for a in audits)
        challenges=sum(a.challenges for a in audits); rebuttals=sum(a.rebuttals for a in audits)
        revisions=sum(a.reevaluations for a in audits); minorities=sum(a.minority for a in audits)
        chains=sum(a.chain_count for a in audits); complete=sum(a.chain_complete for a in audits)
        evidence=sum(a.evidence_turns for a in audits)
        ratios={}
        for s in sessions:
            for t in s.turns: ratios[t.speaker]=ratios.get(t.speaker,0)+1
        ratios={k:v/max(1,turns) for k,v in ratios.items()}
        reasons=[]
        if duplicates: reasons.append('duplicate_sessions')
        if chars<self.min_chars: reasons.append(f'chars_below_100k:{chars}')
        if chains==0 or complete/chains<self.min_complete_chain_ratio: reasons.append('daily_chain_quality_fail')
        if turns and evidence/turns<self.min_evidence_density: reasons.append('daily_evidence_density_fail')
        if any(not a.quality_pass for a in audits): reasons.append('session_quality_fail')
        return {'status':'PASS' if not reasons else 'FAIL','audit_scope':'structural_only',
                'training_achievement_verified':False,
                'duplicate_sessions':duplicates,'unique_sessions':len(sessions),
                'qualified_chars':sum(a.chars for a in audits if a.quality_pass),
                'chars':chars,'turns':turns,'topics':len({(s.race.race_id,s.race.topic) for s in sessions}),
                'challenges':challenges,'rebuttals':rebuttals,'position_revisions':revisions,'minority_opinions':minorities,
                'speaker_ratio':ratios,'chains':chains,'complete_chains':complete,'evidence_turns':evidence,'reasons':reasons}

@dataclass
class LearningCandidate:
    candidate_id:str; source_session:str; category:str; rule:str; evidence_refs:List[str]; status:str='SHADOW_TEST'

class LearningRegistry:
    def __init__(self): self.items:List[LearningCandidate]=[]
    def add(self,item:LearningCandidate):
        if not item.evidence_refs: raise ValueError('learning candidate requires evidence')
        self.items.append(item); return item
    def summary(self):
        return {'total':len(self.items),'shadow_test':sum(x.status=='SHADOW_TEST' for x in self.items),
                'adopted':sum(x.status=='ADOPTED' for x in self.items),'rejected':sum(x.status=='REJECTED' for x in self.items)}

@dataclass(frozen=True)
class SnapshotManifest:
    date:str; expected_races:int; frozen_races:int; snapshot_sha256:str; result_revealed:bool=False
    @property
    def coverage(self): return self.frozen_races/max(1,self.expected_races)
    def assert_reviewable(self):
        if self.coverage<1.0: raise RuntimeError(f'Snapshot incomplete: {self.frozen_races}/{self.expected_races}')

class DailyOrchestrator:
    '''Fail-closed coordinator. Does not fetch races; it enforces sequencing around PRISM data.''' 
    def __init__(self,archive:DiscussionArchive,gate:DailyGate,registry:LearningRegistry):
        self.archive=archive; self.gate=gate; self.registry=registry
    def run_discussion_stage(self,manifest:SnapshotManifest,sessions:List[Session])->dict:
        manifest.assert_reviewable()
        saved=[self.archive.save_session(s) for s in sessions]
        report=self.gate.evaluate(sessions)
        report['snapshot_coverage']=manifest.coverage
        report['archive_files']=len(saved)
        report['archive_sha256']=[x['sha256'] for x in saved]
        report['learning_rules']=self.registry.summary()
        report['next_stage']='LEARNING_EXTRACTION' if report['status']=='PASS' else 'MORE_DISCUSSION_REQUIRED'
        return report
