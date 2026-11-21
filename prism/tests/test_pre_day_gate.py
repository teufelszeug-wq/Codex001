"""Synthetic boundary tests; no fixture represents a real independent execution."""
from copy import deepcopy
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from prism_pre_day_gate import check_publication, append_revision, content_hash
from prism_ops.characters import build_character_snapshot, get_character
from prism_ops.provider import OpenAIProvider


class PublicationGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        snapshot = build_character_snapshot([
            {'agent_id': 'EXPERT', 'name': '架空専門家', 'role': 'SYNTHETIC_TEST',
             'configuration': 'Synthetic fixture only',
             'source_page_url': 'https://www.notion.so/synthetic-test-character'}],
            source_url='https://www.notion.so/synthetic-test-database',
            captured_at='2026-11-14T08:00:00+09:00')
        self.character = get_character(snapshot, 'EXPERT')
        self.race = {'race_id': 'SYNTHETIC-TEST', 'start_at': '2026-11-15T15:40:00+09:00',
                     'runners': [{'horse_id': 'h1', 'horse_no': 1, 'frame_no': 1, 'name': '架空馬A'},
                                 {'horse_id': 'h2', 'horse_no': 2, 'frame_no': 1, 'name': '架空馬B'}],
                     'required_forecasters': ['EXPERT'], 'declaration_stage': 'DRAW_CONFIRMED',
                     'character_snapshot_hash': snapshot['snapshot_hash']}
        self.receipts = {}
        self.counter = 0
        self.preliminary = {'EXPERT': self.execution('PRELIMINARY', '10:00:00')}
        self.topics = []
        for i in range(5):
            self.topics.append({'topic_id': 'topic-' + str(i), 'title': '架空議題' + str(i),
                                'started_at': f'2026-11-14T{11 + i:02}:00:00+09:00',
                                'completed_at': f'2026-11-14T{11 + i:02}:10:00+09:00',
                                'facilitator': 'SHINOMIYA_RITSU', 'newcomer': 'RIO',
                                'turns': [self.execution('RESPONSE', f'{11 + i:02}:05:00',
                                    context_extra={'preliminary': self.preliminary, 'previous_topics': self.topics,
                                                   'topic': {'topic_id': 'topic-' + str(i), 'title': '架空議題' + str(i)},
                                                   'prior_turns': []})]})
        self.final = {'EXPERT': self.execution('FINAL', '18:00:00')}
        self.publication_hash = content_hash({'synthetic_publication_fixture': True})
        pdf = Path(self.temp.name) / 'fixture.pdf'
        png = Path(self.temp.name) / 'fixture.png'
        # Headers exercise artifact binding only. Rendering has separate real PDF/PNG tests.
        pdf.write_bytes(b'%PDF-1.4\nsynthetic unit boundary\n')
        png.write_bytes(b'\x89PNG\r\n\x1a\nsynthetic unit boundary\n')
        descriptor = lambda p: {'path': str(p), 'sha256': sha256(p.read_bytes()).hexdigest()}
        self.paper = {'race_id': self.race['race_id'], 'version': 'synthetic-v1',
                      'content_hash': self.publication_hash,
                      'generated_at': '2026-11-14T18:10:00+09:00',
                      'pdf': descriptor(pdf), 'images': [descriptor(png)],
                      'qa': {'status': 'VERIFIED', 'checked_at': '2026-11-14T18:20:00+09:00',
                             'pages': 1, 'writing_mode': 'vertical-rl',
                             'reviewer': 'SYNTHETIC TEST FIXTURE', 'notes': 'No actual visual approval',
                             'mechanical_checks': {'passed': True, 'font_ready': True,
                                                   'all_text_retained': True, 'errors': [], 'pages': 1}}}
        self.seal_paper()

    def execution(self, stage, clock, *, synthetic=False, context_extra=None, tickets=None):
        self.counter += 1
        context = {'race_id': self.race['race_id'], 'runners': self.race['runners'],
                   'character_snapshot_hash': self.race['character_snapshot_hash'], 'source_refs': ['fixture']}
        if stage == 'FINAL':
            context.update(preliminary=self.preliminary, discussions=self.topics)
        if context_extra:
            context.update(context_extra)
        if stage == 'RESPONSE':
            payload = {'text': '架空テスト発言' + str(self.counter), 'evidence_refs': ['fixture'],
                       'stance': 'CHALLENGE', 'responds_to': None}
        else:
            payload = {'diagnoses': [{'horse_id': 'h1', 'reason': '架空材料A'},
                                     {'horse_id': 'h2', 'reason': '架空材料B'}],
                       'picks': [{'horse_id': 'h1', 'mark': '◎', 'reason': '架空印'}],
                       'tickets': [{'type': 'WIN', 'horse_nos': [1], 'stake_yen': 100}],
                       'skip_reason': '', 'change_reason': '維持理由' if stage == 'FINAL' else ''}
            if tickets is not None:
                payload['tickets'] = tickets
        response = {'id': 'SYNTHETIC-HTTP-FIXTURE-' + str(self.counter), 'status': 'completed', 'model': 'SYNTHETIC-UNIT-TEST',
                    'output': [{'type': 'message', 'content': [{'type': 'output_text',
                                'text': json.dumps(payload, ensure_ascii=False)}]}]}
        provider = OpenAIProvider(model='SYNTHETIC-UNIT-TEST', api_key='SYNTHETIC-UNIT-TEST',
                                  now=lambda: '2026-11-14T' + clock + '+09:00',
                                  transport=(lambda body, timeout: response) if synthetic else None)
        # Mock HTTP at the network boundary to cover the production receipt validator.
        # These are unit fixtures, never executed/verified real forecast records.
        with patch.object(provider, '_https', return_value=response):
            result = provider.predict(context, self.character, stage=stage)
        result['persisted_at'] = result['output']['saved_at']
        self.receipts[result['receipt']['execution_id']] = result
        return result['output']

    def seal_paper(self):
        qa = self.paper['qa']
        qa['qa_hash'] = content_hash({k: v for k, v in qa.items() if k != 'qa_hash'})
        self.paper['manifest_hash'] = content_hash({k: v for k, v in self.paper.items() if k != 'manifest_hash'})

    def check(self, **kwargs):
        args = dict(execution_receipts=self.receipts, paper=self.paper,
                    publication_content_hash=self.publication_hash,
                    checked_at='2026-11-14T21:00:00+09:00')
        args.update(kwargs)
        return check_publication(self.race, self.preliminary, self.topics, self.final,
                                 '2026-11-14T20:00:00+09:00', **args)

    def test_complete_structurally_bound_synthetic_http_fixture(self):
        self.assertEqual(self.check()['errors'], [])

    def test_entry_stage_cannot_publish_even_if_numbers_were_filled(self):
        self.race['declaration_stage'] = 'ENTRIES_CONFIRMED'
        self.assertIn('DRAW_NOT_CONFIRMED', self.check()['errors'])

    def test_draw_label_without_confirmed_frames_is_rejected(self):
        self.race['runners'][0]['frame_no'] = None
        self.assertIn('RUNNER_DRAW_INCOMPLETE', self.check()['errors'])

    def test_legacy_empty_records_and_invented_id_do_not_publish(self):
        final = {'EXPERT': {'mode': 'independent_execution', 'execution_id': 'invented',
                           'saved_at': '2026-11-15T15:30:00+09:00', 'picks': ['A']}}
        result = check_publication(self.race, {'EXPERT': {}}, [1, 1, 1, 1, 1], final,
                                   '2026-11-14T20:00:00+09:00', checked_at='2026-11-14T21:00:00+09:00')
        self.assertFalse(result['ready'])
        self.assertIn('FIVE_DISTINCT_TOPICS_REQUIRED', result['errors'])

    def test_final_executed_after_publication_fails(self):
        self.final['EXPERT'] = self.execution('FINAL', '20:01:00')
        self.assertIn('FORECAST_AFTER_PUBLICATION:FINAL:EXPERT', self.check()['errors'])

    def test_final_executed_before_topics_finish_fails(self):
        self.final['EXPERT'] = self.execution('FINAL', '14:00:00')
        self.assertIn('FINAL_BEFORE_DISCUSSION_COMPLETE', self.check()['errors'])

    def test_discussion_before_all_initial_predictions_saved_fails(self):
        self.preliminary['EXPERT'] = self.execution('PRELIMINARY', '12:00:00')
        self.assertIn('INVALID_DISCUSSION_TOPIC', self.check()['errors'])

    def test_duplicate_topic_is_not_five_topics(self):
        self.topics[4] = deepcopy(self.topics[0])
        self.assertIn('FIVE_DISTINCT_TOPICS_REQUIRED', self.check()['errors'])

    def test_missing_required_specialist_fails(self):
        self.race['required_forecasters'].append('ABSENT')
        self.assertIn('FINAL_FORECASTER_COVERAGE', self.check()['errors'])

    def test_final_receipt_must_include_the_actual_discussion_inputs(self):
        altered = deepcopy(self.topics)
        altered[0]['title'] = '別の入力'
        self.final['EXPERT'] = self.execution('FINAL', '18:00:00', context_extra={'discussions': altered})
        self.assertIn('FINAL_INPUT_DEPENDENCY_MISMATCH:EXPERT', self.check()['errors'])

    def test_synthetic_transport_cannot_be_claimed_independent(self):
        self.final['EXPERT'] = self.execution('FINAL', '18:00:00', synthetic=True)
        self.assertIn('EXECUTION_UNPROVEN:FINAL:EXPERT', self.check()['errors'])

    def test_durable_save_receipt_is_required(self):
        self.receipts[self.final['EXPERT']['execution_id']].pop('persisted_at')
        self.assertIn('EXECUTION_UNPROVEN:FINAL:EXPERT', self.check()['errors'])

    def test_receipt_input_or_character_tampering_fails(self):
        self.receipts[self.final['EXPERT']['execution_id']]['context']['race_id'] = 'other'
        self.assertIn('EXECUTION_UNPROVEN:FINAL:EXPERT', self.check()['errors'])

    def test_all_horses_and_100_yen_units_required(self):
        self.final['EXPERT']['diagnoses'].pop()
        self.final['EXPERT']['tickets'][0]['stake_yen'] = 150
        errors = self.check()['errors']
        self.assertIn('ALL_RUNNER_DIAGNOSES_REQUIRED:FINAL:EXPERT', errors)
        self.assertIn('INVALID_TICKET:FINAL:EXPERT', errors)

    def test_same_frame_pair_uses_frame_numbers_without_aliasing_horses(self):
        self.final['EXPERT'] = self.execution('FINAL', '18:00:00', tickets=[
            {'type': 'FRAME_QUINELLA', 'frame_nos': [1, 1], 'stake_yen': 100}])
        self.assertEqual(self.check()['errors'], [])
        self.final['EXPERT']['tickets'][0]['horse_nos'] = [1, 2]
        self.assertIn('INVALID_TICKET:FINAL:EXPERT', self.check()['errors'])

    def test_prediction_changes_require_reason(self):
        self.final['EXPERT']['tickets'][0]['stake_yen'] = 200
        self.final['EXPERT']['change_reason'] = ''
        self.assertIn('CHANGE_REASON_REQUIRED:EXPERT', self.check()['errors'])

    def test_mechanical_execution_only_is_not_visual_qa(self):
        self.paper['qa']['status'] = 'EXECUTED'
        self.seal_paper()
        self.assertIn('PAPER_PDF_IMAGE_QA_UNVERIFIED', self.check()['errors'])

    def test_failed_mechanical_checks_cannot_be_promoted_by_visual_label(self):
        self.paper['qa']['mechanical_checks']['all_text_retained'] = False
        self.seal_paper()
        self.assertIn('PAPER_PDF_IMAGE_QA_UNVERIFIED', self.check()['errors'])

    def test_modified_pdf_or_missing_page_fails(self):
        Path(self.paper['pdf']['path']).write_bytes(b'%PDF-1.4 changed')
        self.assertIn('PAPER_PDF_IMAGE_QA_UNVERIFIED', self.check()['errors'])

    def test_wrong_paper_bundle_fails(self):
        self.paper['content_hash'] = '0' * 64
        self.seal_paper()
        self.assertIn('PAPER_PDF_IMAGE_QA_UNVERIFIED', self.check()['errors'])

    def test_naive_invalid_and_future_publication_fail_closed(self):
        for value in ['bad', '2026-11-14T20:00:00', '2026-11-15T15:41:00+09:00']:
            result = check_publication(self.race, self.preliminary, self.topics, self.final, value,
                                       checked_at='2026-11-14T21:00:00+09:00')
            self.assertFalse(result['ready'])

    def test_jst_date_boundary_is_used_for_preceding_day(self):
        result = check_publication(self.race, self.preliminary, self.topics, self.final,
                                   '2026-11-14T15:00:00Z', checked_at='2026-11-15T01:00:00+09:00')
        self.assertIn('LATE_PUBLICATION', result['errors'])


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.old = {'race_id': 'SYNTHETIC-TEST', 'version': 'v1',
                    'saved_at': '2026-11-14T18:00:00+09:00', 'predictions': ['original']}
        self.new = {'race_id': 'SYNTHETIC-TEST', 'version': 'v2',
                    'saved_at': '2026-11-15T08:00:00+09:00',
                    'base_sha256': content_hash(self.old), 'previous_sha256': content_hash(self.old),
                    'changes': {'body_weight': {'horse_no': 1, 'before': None, 'after': 480}},
                    'change_reason': '公式馬体重の発表'}

    def test_revision_keeps_base_and_detaches_mutable_callers(self):
        out = append_revision([self.old], self.new)
        out[0]['predictions'].append('mutated')
        self.assertEqual(self.old['predictions'], ['original'])
        self.assertEqual(out[1]['base_sha256'], content_hash(self.old))

    def test_prediction_rewrite_or_unbound_base_rejected(self):
        for key, value in [('base_sha256', 'invented'), ('change_reason', ''),
                           ('changes', {'predictions': []}), ('predictions', ['replacement'])]:
            invalid = dict(self.new, **{key: value})
            with self.assertRaises(ValueError):
                append_revision([self.old], invalid)

    def test_mutating_base_after_a_delta_invalidates_the_chain(self):
        history = append_revision([self.old], self.new)
        history[0]['predictions'] = ['changed base']
        third = dict(self.new, version='v3', saved_at='2026-11-15T09:00:00+09:00',
                     base_sha256=content_hash(history[0]), previous_sha256=content_hash(history[-1]))
        with self.assertRaisesRegex(ValueError, 'history integrity'):
            append_revision(history, third)

    def test_legacy_replay_must_be_explicit(self):
        old = {'version': 'v1', 'saved_at': '2026-11-14T18:00:00+09:00'}
        new = {'version': 'v2', 'saved_at': '2026-11-15T08:00:00+09:00'}
        with self.assertRaises(ValueError):
            append_revision([old], new)
        self.assertEqual(append_revision([old], new, legacy=True), [old, new])


if __name__ == '__main__':
    unittest.main()
