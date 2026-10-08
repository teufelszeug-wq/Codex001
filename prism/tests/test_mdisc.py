from pathlib import Path
from prism_mdisc.core import *

def sample():
    race=RaceContext('FUN11','日本テレビ盃','船橋',1800,'JpnII','ConfidenceとValueの分離')
    moves=[Move.QUESTION,Move.CLAIM,Move.CHALLENGE,Move.EVIDENCE,Move.COUNTER_EVIDENCE,Move.REBUTTAL,Move.REEVALUATION,Move.MINORITY,Move.RIO_SUMMARY]
    turns=[]
    speakers=['りお','能力AI','反証AI','能力AI','ValueAI','能力AI','能力AI','ValueAI','りお']
    for i,(m,sp) in enumerate(zip(moves,speakers)):
        turns.append(Turn(sp,'司会' if sp=='りお' else '専門',m,('7 ミッキーファイト ' if i==0 else '')+'検証本文'*80,
                          evidence_type=EvidenceType.DATA if m in (Move.EVIDENCE,Move.COUNTER_EVIDENCE) else None))
    return Session('s01',race,['りお','能力AI','反証AI','ValueAI'],turns)

def test_quality_chain():
    a=audit_session(sample()); assert a.chain_complete==1

def test_100k_gate_fails_when_short():
    r=DailyGate().evaluate([sample()]); assert r['status']=='FAIL'; assert any('chars_below_100k' in x for x in r['reasons'])

def test_archive_hash(tmp_path):
    x=DiscussionArchive(tmp_path).save_session(sample()); assert len(x['sha256'])==64

def test_incomplete_snapshot_blocks_discussion(tmp_path):
    o=DailyOrchestrator(DiscussionArchive(tmp_path),DailyGate(),LearningRegistry())
    m=SnapshotManifest('2026-09-30',48,37,'abc')
    try: o.run_discussion_stage(m,[sample()]); assert False
    except RuntimeError: pass

def test_learning_requires_evidence():
    r=LearningRegistry()
    try: r.add(LearningCandidate('x','s','pace','change',[])); assert False
    except ValueError: pass
