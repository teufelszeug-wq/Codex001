import copy
import tempfile
import unittest
from pathlib import Path
from hashlib import sha256
from prism_mdisc.core import *
from prism_mdisc.evidence_audit import Evidence, audit_race, REQUIRED_TOPICS

def fixture(topic='all_horses', sid='s0'):
    people=['りお','分析役','反証役']
    moves=[Move.QUESTION,Move.CLAIM,Move.CHALLENGE,Move.EVIDENCE,Move.REBUTTAL,Move.COUNTER_EVIDENCE,Move.REEVALUATION,Move.REEVALUATION,Move.RIO_SUMMARY]
    turns=[Turn(people[i%3],'テスト担当',m,f'{topic} 検査専用発言 {i}。',horse_ids=['h1'],evidence_type=EvidenceType.DATA if i in (3,5) else None,evidence_ref='e1' if i in (3,5) else None) for i,m in enumerate(moves)]
    return Session(sid,RaceContext('r1','架空','テスト',1600,'架空条件',topic),people,turns)

def bundle():
    sessions=[fixture(t,f's{i}') for i,t in enumerate(REQUIRED_TOPICS)]
    text='架空資料。実レースではない。'
    e=Evidence('e1','synthetic',text,sha256(text.encode()).hexdigest(),'2026-01-01T08:00:00+09:00','2026-01-01T08:01:00+09:00','synthetic')
    j=[]
    for i,a in enumerate(sessions[0].participants):
        j.append({'horse_id':'h1','ai_id':a,'initial':{'session_id':'s0','turn_index':i},'response':{'session_id':'s0','turn_index':i+3,'responds_to':1 if i==0 else i-1},'final':{'session_id':'s0','turn_index':i+6}})
    return dict(race_id='r1',horse_ids=['h1'],ai_ids=sessions[0].participants,sessions=sessions,topic_by_session={s.session_id:s.race.topic for s in sessions},evidence=[e],cutoff='2026-01-01T09:00:00+09:00',judgments=j)

class AuditRegression(unittest.TestCase):
    def test_revealed_results_rejected_before_archive(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            worker=DailyOrchestrator(DiscussionArchive(root),DailyGate(),LearningRegistry())
            with self.assertRaisesRegex(RuntimeError,'result-revealed'):
                worker.run_discussion_stage(SnapshotManifest('2026-01-01',1,1,'fixture',True),[fixture()])
            self.assertEqual(list(root.iterdir()),[])

    def test_reversed_chain_fails_session_and_daily_gate(self):
        s=fixture()
        s.turns[:-1]=reversed(s.turns[:-1])
        self.assertEqual(audit_session(s).chain_complete,0)
        self.assertFalse(audit_session(s).quality_pass)
        self.assertEqual(DailyGate(min_chars=1).evaluate([s])['status'],'FAIL')

    def test_intervening_discussion_preserves_ordered_chain(self):
        s=fixture()
        s.turns.insert(2,Turn('反証役','専門',Move.QUESTION,'追加の問い',evidence_type=EvidenceType.DATA,evidence_ref='e1'))
        self.assertTrue(audit_session(s).quality_pass)

    def test_repeat_does_not_increase_total(self):
        s=fixture();report=DailyGate(min_chars=1).evaluate([s]*35)
        self.assertEqual(report['status'],'FAIL')
        self.assertEqual(report['chars'],sum(len(t.text) for t in s.turns))
        self.assertEqual(report['unique_sessions'],1)
        self.assertEqual(report['duplicate_sessions'],34)

    def test_rename_and_whitespace_do_not_evade(self):
        a=fixture();b=copy.deepcopy(a);b.session_id='new';b.turns[0].text=' '+b.turns[0].text+'\n'
        self.assertEqual(DailyGate(min_chars=1).evaluate([a,b])['unique_sessions'],1)

    def test_missing_evidence_fails(self):
        s=fixture();s.turns[3].evidence_ref=None
        self.assertFalse(audit_session(s).quality_pass)

    def test_large_roster_allowed(self):
        s=fixture();s.participants+=['追加1','追加2','追加3','追加4']
        # Additional participants must actually speak, not just appear in metadata.
        s.turns[0:0]=[Turn(p,'専門',Move.QUESTION,'追加の確認'+p) for p in s.participants[3:]]
        s.turns[0].evidence_type=EvidenceType.DATA;s.turns[0].evidence_ref='e1'
        self.assertTrue(audit_session(s).quality_pass)

    def test_archive_immutable_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            archive=DiscussionArchive(Path(d));s=fixture()
            self.assertEqual(archive.save_session(s),archive.save_session(s))
            s.turns[0].text+='changed'
            with self.assertRaises(ValueError):archive.save_session(s)
            s.session_id='../escape'
            with self.assertRaises(ValueError):archive.save_session(s)

    def test_five_topic_structural_pass(self):
        result=audit_race(**bundle());self.assertEqual(result['status'],'STRUCTURAL_PASS',result)
        self.assertFalse(result['training_achievement_verified'])
        self.assertEqual(result['judgment_coverage']['complete'],3)

    def test_missing_topic_not_complete(self):
        b=bundle();b['sessions'].pop()
        self.assertEqual(audit_race(**b)['missing_topics'],['tickets'])

    def test_future_and_hash_mismatch(self):
        from dataclasses import replace
        for change in ({'available_at':'2026-01-02T00:00:00Z'},{'content_sha256':'0'*64}):
            b=bundle();b['evidence']=[replace(b['evidence'][0],**change)]
            self.assertEqual(audit_race(**b)['status'],'FAIL')

    def test_unresolved_source(self):
        b=bundle();b['sessions'][0].turns[3].evidence_ref='missing'
        self.assertEqual(audit_race(**b)['status'],'FAIL')

    def test_response_and_horse_coverage(self):
        b=bundle();b['judgments'][0]['response']['responds_to']=0
        self.assertEqual(audit_race(**b)['status'],'FAIL')
        b=bundle();b['horse_ids'].append('h2')
        self.assertEqual(len(audit_race(**b)['judgment_coverage']['missing']),3)

    def test_invalidated_records_not_counted(self):
        b=bundle();before=audit_race(**b);b['invalidated_ids']=['s4'];after=audit_race(**b)
        self.assertEqual(after['valid_sessions'],4)
        self.assertLess(after['valid_chars'],before['valid_chars'])
        self.assertEqual(after['status'],'FAIL')

    def test_wrong_race_and_judgment_order(self):
        from dataclasses import replace
        b=bundle();b['sessions'][0].race=replace(b['sessions'][0].race,race_id='r2');self.assertEqual(audit_race(**b)['status'],'FAIL')
        b=bundle();b['judgments'][0]['final']['turn_index']=0;self.assertEqual(audit_race(**b)['status'],'FAIL')

if __name__=='__main__':unittest.main()
