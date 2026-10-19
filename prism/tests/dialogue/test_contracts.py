"""Synthetic contract fixtures; not specialist executions or training records."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
sys.path.insert(0, str(ROOT/'tests/engine'))
from fixture import raw_fixture
from prism_engine import predict
from prism_engine.contracts import digest
from prism_dialogue import build_discussion_context, validate_discussion, review_learning


def make_context():
    raw = raw_fixture()
    p = predict(raw, '2026-01-01T09:55:00+09:00')
    return build_discussion_context({'schema': 'prism.engine.bundle/v1', 'prediction': p, 'raw': raw})


def records_fixture(context):
    r = {'schema': 'prism.dialogue.records/v1',
         **{k: context[k] for k in ('race_id', 'input_hash', 'prediction_hash')},
         'recorded_at': '2026-01-01T09:59:00+09:00', 'execution_mode': 'TEMPLATE',
         'required_agents': ['TEST_ABILITY', 'TEST_COURSE'], 'facilitator': 'SHINOMIYA_RITSU',
         'newcomer': 'RIO', 'evidence': [], 'turns': []}
    ref = context['evidence'][0]['evidence_id']
    def add(agent, horse, stage, theme, reply=None, stance='SUPPORT'):
        tid = f't{len(r["turns"])}'
        r['turns'].append({'turn_id': tid, 'agent_id': agent, 'horse_id': horse,
                           'stage': stage, 'theme': theme, 'text': f'SYNTHETIC {tid} {agent} {horse} {stage}',
                           'evidence_refs': [ref], 'responds_to': reply, 'stance': stance,
                           'invalidation_condition': 'SYNTHETIC: supplied condition changes'})
        return tid
    add('SHINOMIYA_RITSU', None, 'INTRO', 'COURSE')
    for horse in (h['horse_id'] for h in context['roster']):
        a = add('TEST_ABILITY', horse, 'INITIAL', 'DIAGNOSIS')
        b = add('TEST_COURSE', horse, 'INITIAL', 'INFORMATION')
        question = add('RIO', horse, 'QUESTION', 'INFORMATION', a, 'QUESTION')
        add('TEST_ABILITY', horse, 'RESPONSE', 'CASE', b, 'CHALLENGE')
        add('TEST_COURSE', horse, 'RESPONSE', 'CASE', a, 'MINORITY')
        add('TEST_ABILITY', horse, 'RESPONSE', 'INFORMATION', question, 'SUPPORT')
        add('TEST_ABILITY', horse, 'FINAL', 'BETS')
        add('TEST_COURSE', horse, 'FINAL', 'BETS')
        add('RIO', horse, 'FINAL', 'BETS')
    return r


class DiscussionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.context = make_context()
    def audit(self, records): return validate_discussion(self.context, records)
    def test_valid_template_never_training_or_independent_count(self):
        r = records_fixture(self.context); a = self.audit(r)
        self.assertEqual(a['status'], 'STRUCTURAL_PASS', a['errors'])
        self.assertEqual(a['counts']['verified_independent_sessions'], 0)
        self.assertFalse(a['training_achievement_verified'])
        r['execution_mode'] = 'INDEPENDENT_EXECUTION'
        self.assertFalse(self.audit(r)['independent_execution_verified'])
    def test_result_bundle_rejected(self):
        p = self.context['evidence'][0]['content']
        with self.assertRaises(ValueError): build_discussion_context({'schema': 'prism.engine.bundle/v1', 'prediction': p, 'settlement': {}})
    def test_binding_wrong_version_fails(self):
        r = records_fixture(self.context); r['prediction_hash'] = 'other'
        self.assertIn('BINDING', self.audit(r)['errors'])
    def test_prediction_integrity(self):
        p = deepcopy(self.context['evidence'][0]['content']); p['win']['h1'] = .9
        with self.assertRaises(ValueError): build_discussion_context({'schema': 'prism.engine.bundle/v1', 'prediction': p})
    def test_resealed_prediction_numbering_cannot_override_raw(self):
        raw = raw_fixture()
        for field in ('horse_no', 'frame_no', 'barrier_no'):
            p = deepcopy(self.context['evidence'][0]['content'])
            p['features']['horses']['h1'][field] = 99
            p['lock_hash'] = digest({k:v for k,v in p.items() if k != 'lock_hash'})
            with self.subTest(field=field), self.assertRaises(ValueError):
                build_discussion_context({'schema': 'prism.engine.bundle/v1', 'prediction': p, 'raw': raw})
    def test_resealed_prediction_frame_map_cannot_override_raw(self):
        p = deepcopy(self.context['evidence'][0]['content']); p['frames']['h1'] = '8'
        p['lock_hash'] = digest({k:v for k,v in p.items() if k != 'lock_hash'})
        with self.assertRaises(ValueError):
            build_discussion_context({'schema': 'prism.engine.bundle/v1', 'prediction': p, 'raw': raw_fixture()})
    def test_resealed_runner_set_cannot_override_raw(self):
        p = deepcopy(self.context['evidence'][0]['content'])
        p['features']['horses']['other'] = p['features']['horses'].pop('h1')
        p['win']['other'] = p['win'].pop('h1')
        p['lock_hash'] = digest({k:v for k,v in p.items() if k != 'lock_hash'})
        with self.assertRaises(ValueError):
            build_discussion_context({'schema': 'prism.engine.bundle/v1', 'prediction': p, 'raw': raw_fixture()})
    def test_unknown_pre_result_fields(self):
        r = records_fixture(self.context); r['result'] = {'winner': 'h1'}
        self.assertEqual(self.audit(r)['status'], 'FAIL')
    def test_coverage_requires_every_specialist_every_horse(self):
        r = records_fixture(self.context); r['turns'].pop(-2)
        self.assertIn('ALL_AGENT_ALL_HORSE_COVERAGE', self.audit(r)['errors'])
    def test_response_must_link_other_speaker_same_horse(self):
        r = records_fixture(self.context); r['turns'][4]['responds_to'] = 'missing'
        self.assertIn('BROKEN_RESPONSE', self.audit(r)['errors'])
    def test_invalidated_conclusion_condition_required(self):
        r = records_fixture(self.context); r['turns'][-1]['invalidation_condition'] = ''
        self.assertIn('MISSING_INVALIDATION_CONDITION', self.audit(r)['errors'])
    def test_duplicate_turn_and_text(self):
        r = records_fixture(self.context); r['turns'].append(deepcopy(r['turns'][0]))
        a = self.audit(r)
        self.assertIn('DUPLICATE_OR_EMPTY_TURN', a['errors']); self.assertIn('DUPLICATE_TEXT', a['errors'])
    def test_broken_evidence_reference(self):
        r = records_fixture(self.context); r['turns'][1]['evidence_refs'] = ['unknown']
        self.assertIn('BROKEN_EVIDENCE_REF', self.audit(r)['errors'])
    def test_future_or_result_evidence_fails(self):
        for kind, when, code in [('RESULT', '2026-01-01T09:00:00+09:00', 'RESULT_EVIDENCE_IN_PRE'),
                                 ('PRE_SOURCE', '2026-01-01T11:00:00+09:00', 'FUTURE_EVIDENCE')]:
            r = records_fixture(self.context)
            r['evidence'] = [{'evidence_id': 'x', 'kind': kind, 'content': 'test', 'content_hash': digest('test'),
                              'available_at': when, 'horse_ids': ['h1']}]
            self.assertIn(code, self.audit(r)['errors'])
    def test_five_themes_required(self):
        r = records_fixture(self.context)
        for t in r['turns']: t['theme'] = 'DIAGNOSIS'
        self.assertIn('FIVE_THEMES_REQUIRED', self.audit(r)['errors'])
    def test_disguised_result_evidence_fails(self):
        r = records_fixture(self.context); content = {'nested': {'winner': 'h1'}}
        r['evidence'] = [{'evidence_id': 'x', 'kind': 'PRE_SOURCE', 'content': content,
                          'content_hash': digest(content), 'available_at': self.context['locked_at'], 'horse_ids': ['h1']}]
        self.assertIn('RESULT_FIELDS_IN_PRE', self.audit(r)['errors'])
    def test_rio_final_follows_question(self):
        r = records_fixture(self.context)
        r['turns'] = [t for t in r['turns'] if t['agent_id'] != 'RIO' or t['stage'] != 'QUESTION']
        self.assertIn('RIO_FINAL_WITHOUT_QUESTION', self.audit(r)['errors'])
    def test_rio_questions_require_expert_reply(self):
        r = records_fixture(self.context)
        questions = {t['turn_id'] for t in r['turns'] if t['agent_id'] == 'RIO' and t['stage'] == 'QUESTION'}
        r['turns'] = [t for t in r['turns'] if t['responds_to'] not in questions]
        self.assertIn('RIO_QUESTION_UNANSWERED', self.audit(r)['errors'])
    def test_roles_preserved(self):
        r = records_fixture(self.context); r['newcomer'] = 'EDITOR'
        self.assertIn('ROLE_ASSIGNMENT', self.audit(r)['errors'])
    def test_optional_rio_selection_requires_matching_final(self):
        r = records_fixture(self.context)
        final = next(t for t in r['turns'] if t['agent_id'] == 'RIO' and t['stage'] == 'FINAL')
        r['selections'] = [{k: final[k] for k in ('agent_id', 'horse_id', 'turn_id')} | {'selection': 'TOP_PICK'}]
        self.assertEqual(self.audit(r)['status'], 'STRUCTURAL_PASS')
        r['selections'][0]['horse_id'] = 'wrong'
        self.assertIn('SELECTION_FINAL_BINDING', self.audit(r)['errors'])
    def test_selection_not_inferred_from_prose(self):
        r = records_fixture(self.context); r['turns'][-1]['text'] = 'この馬を本命にします。'
        before = digest(r); self.audit(r)
        self.assertNotIn('selections', r); self.assertEqual(before, digest(r))
    def test_duplicate_selection_and_multiple_top_pick_rejected(self):
        r = records_fixture(self.context)
        finals = [t for t in r['turns'] if t['agent_id'] == 'RIO' and t['stage'] == 'FINAL']
        r['selections'] = [{k: t[k] for k in ('agent_id', 'horse_id', 'turn_id')} | {'selection': 'TOP_PICK'} for t in finals[:2]]
        self.assertIn('MULTIPLE_TOP_PICKS', self.audit(r)['errors'])
        r['selections'] = [r['selections'][0], deepcopy(r['selections'][0])]
        self.assertIn('DUPLICATE_SELECTION', self.audit(r)['errors'])
    def test_malformed_records_fail_closed(self):
        for malformed in [None, {}, {'turns': None}]:
            self.assertEqual(self.audit(malformed)['status'], 'FAIL')
    def test_review_cannot_change_pre_or_claim_learning(self):
        c = deepcopy(self.context); r = records_fixture(c); before = digest([c, r])
        result = {'race_id': c['race_id'], 'prediction_hash': c['prediction_hash'],
                  'available_at': '2026-01-01T10:10:00+09:00', 'winners': ['h1']}
        result['content_hash'] = digest(result)
        review = review_learning(c, r, result)
        self.assertEqual(before, digest([c, r])); self.assertFalse(review['model_parameters_changed'])
        self.assertFalse(review['forward_performance_verified'])
        result['prediction_hash'] = 'other'; result['content_hash'] = digest({k:v for k,v in result.items() if k!='content_hash'})
        with self.assertRaises(ValueError): review_learning(c, r, result)


if __name__ == '__main__': unittest.main()
