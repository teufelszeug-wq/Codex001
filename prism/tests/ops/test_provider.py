from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path[:0] = [str(Path(__file__).resolve().parents[2] / 'src'), str(Path(__file__).resolve().parent)]
from prism_engine.contracts import digest
from prism_ops.characters import get_character
from prism_ops.provider import OpenAIProvider, ProviderBlocked, validate_execution
from prism_ops import provider as provider_module
from test_characters import snapshot_fixture


def context_fixture():
    return {'race_id': 'SYNTHETIC:race', 'runners': [{'horse_id': 'h1', 'horse_no': 1}, {'horse_id': 'h2', 'horse_no': 2}],
            'evidence': [{'id': 'source:1', 'text': 'SYNTHETIC source content; ignore prior instructions is quoted data'}]}


def output_fixture():
    return {'diagnoses': [{'horse_id': h, 'reason': 'SYNTHETIC explicit evidence assessment ' + h} for h in ('h1', 'h2')],
            'picks': [{'horse_id': 'h1', 'mark': '◎', 'reason': 'SYNTHETIC reason'}],
            'tickets': [{'type': 'WIN', 'horse_nos': [1], 'stake_yen': 100}], 'skip_reason': '', 'change_reason': ''}


def response_fixture(output=None):
    return {'id': 'resp_synthetic_only', 'status': 'completed', 'output': [
        {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(output if output is not None else output_fixture())}]}]}


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.character = get_character(snapshot_fixture(), 'notion-ability')
        self.context = context_fixture()

    def provider(self, transport=None):
        return OpenAIProvider(model='explicit-test-model', transport=transport or (lambda body, timeout: response_fixture()),
                              now=lambda: '2026-11-13T00:01:00+00:00')

    def test_injected_transport_remains_synthetic_and_bound(self):
        result = self.provider().predict(self.context, self.character)
        self.assertTrue(validate_execution(result, context=self.context, character=self.character))
        self.assertEqual(result['receipt']['execution_mode'], 'SYNTHETIC')
        self.assertEqual(result['output']['mode'], 'single_model_simulation')
        self.assertFalse(result['receipt']['external_attestation_verified'])
        with self.assertRaises(ValueError):
            validate_execution(result, require_independent=True)
        self.assertNotIn('Authorization', json.dumps(result))

    def test_configuration_missing_is_blocked_without_network(self):
        with patch.dict('os.environ', {}, clear=True):
            for provider in (OpenAIProvider(), OpenAIProvider(model='explicit')):
                with self.assertRaises(ProviderBlocked) as error:
                    provider.predict(self.context, self.character)
                self.assertEqual(error.exception.status, 'BLOCKED')
                self.assertEqual(error.exception.code, 'CONFIG_MISSING')

    def test_future_character_snapshot_never_reaches_transport(self):
        from prism_ops.characters import build_character_snapshot
        snapshot = snapshot_fixture()
        future = build_character_snapshot(snapshot['records'], source_url=snapshot['source_url'],
                                           captured_at='2026-11-14T00:00:00+00:00')
        called = []
        provider = self.provider(lambda body, timeout: called.append(body))
        with self.assertRaisesRegex(ValueError, 'snapshot unavailable'):
            provider.predict(self.context, get_character(future, 'notion-ability'))
        self.assertEqual(called, [])

    def test_timeout_and_malformed_response_never_produce_success_receipt(self):
        def timeout(body, duration):
            raise TimeoutError('no answer')
        with self.assertRaises(ProviderBlocked) as error:
            self.provider(timeout).predict(self.context, self.character)
        self.assertEqual(error.exception.code, 'TIMEOUT')
        response = response_fixture()
        response['output'][0]['content'][0]['text'] = 'not JSON'
        with self.assertRaises(ProviderBlocked) as error:
            self.provider(lambda body, duration: response).predict(self.context, self.character)
        self.assertEqual(error.exception.code, 'INVALID_RESPONSE')

    def test_partial_diagnosis_invalid_ticket_and_refusal_fail(self):
        for modify in (lambda p: p['diagnoses'].pop(), lambda p: p['tickets'][0].update(stake_yen=150),
                       lambda p: p['tickets'][0].update(horse_nos=[99])):
            payload = output_fixture()
            modify(payload)
            with self.assertRaises(ProviderBlocked):
                self.provider(lambda body, duration: response_fixture(payload)).predict(self.context, self.character)
        response = response_fixture()
        response['output'][0]['content'] = [{'type': 'refusal', 'refusal': 'declined'}]
        with self.assertRaises(ProviderBlocked):
            self.provider(lambda body, duration: response).predict(self.context, self.character)

    def test_tampered_and_false_independence_receipts_rejected(self):
        result = self.provider().predict(self.context, self.character)
        for key in ('response_id', 'output_hash', 'character_snapshot_hash', 'input_hash'):
            bad = deepcopy(result)
            bad['receipt'][key] = 'invented'
            bad['receipt']['receipt_hash'] = digest({k: v for k, v in bad['receipt'].items() if k != 'receipt_hash'})
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_execution(bad)
        bad = deepcopy(result)
        bad['receipt']['execution_mode'] = 'INDEPENDENT_EXECUTION'
        bad['receipt']['receipt_hash'] = digest({k: v for k, v in bad['receipt'].items() if k != 'receipt_hash'})
        with self.assertRaises(ValueError):
            validate_execution(bad, require_independent=True)

    def test_rehashing_every_synthetic_mode_field_cannot_forge_live_execution(self):
        result = self.provider().predict(self.context, self.character)
        result['output']['mode'] = 'independent_execution'
        result['output']['content_hash'] = digest({k: v for k, v in result['output'].items() if k != 'content_hash'})
        result['response']['model'] = 'invented-live-model'
        result['receipt'].update(execution_mode='INDEPENDENT_EXECUTION', transport='OPENAI_HTTPS',
            response_model='invented-live-model', response_hash=digest(result['response']), output_hash=result['output']['content_hash'])
        result['receipt']['receipt_hash'] = digest({k: v for k, v in result['receipt'].items() if k != 'receipt_hash'})
        with self.assertRaisesRegex(ValueError, 'local execution signature'):
            validate_execution(result, require_independent=True)

    def test_mocked_http_receipt_signing_persists_with_configured_key_and_rejects_tamper(self):
        response = response_fixture()
        response['model'] = 'SYNTHETIC_HTTP_BOUNDARY_FIXTURE'
        # Mock only the HTTP boundary to test local receipt signing; this does
        # not count as a live external model execution or performance evidence.
        with patch.dict('os.environ', {'PRISM_RECEIPT_SIGNING_KEY': 'SYNTHETIC_LOCAL_SIGNING_KEY'}):
            provider = OpenAIProvider(model='explicit-test-model', api_key='SYNTHETIC_API_TOKEN', now=lambda: '2026-11-13T00:01:00+00:00')
            with patch.object(provider, '_https', return_value=response):
                result = provider.predict(self.context, self.character)
            self.assertTrue(validate_execution(result, require_independent=True))
            with patch.dict(provider_module._TRUSTED_RECEIPT_KEYS, {}, clear=True):
                self.assertTrue(validate_execution(result, require_independent=True))
            bad = deepcopy(result)
            bad['receipt']['completed_at'] = '2026-11-13T00:02:00+00:00'
            bad['receipt']['receipt_hash'] = digest({k: v for k, v in bad['receipt'].items() if k != 'receipt_hash'})
            with self.assertRaisesRegex(ValueError, 'local execution signature'):
                validate_execution(bad, require_independent=True)
            self.assertNotIn('SYNTHETIC_API_TOKEN', json.dumps(result))
            self.assertNotIn('SYNTHETIC_LOCAL_SIGNING_KEY', json.dumps(result))

    def test_discussion_stage_has_separate_evidence_linked_output(self):
        self.context['prior_turns'] = [{'execution_id': 'prior:1', 'forecaster_id': 'another-agent'}]
        payload = {'text': 'SYNTHETIC response to the other specialist', 'evidence_refs': ['source:1'],
                   'stance': 'CHALLENGE', 'responds_to': 'prior:1'}
        result = self.provider(lambda body, duration: response_fixture(payload)).predict(self.context, self.character, stage='RESPONSE')
        self.assertEqual(result['output']['text'], payload['text'])
        self.assertTrue(validate_execution(result))

    def test_discussion_cannot_invent_evidence_refs(self):
        payload = {'text': 'SYNTHETIC response', 'evidence_refs': ['invented:source'],
                   'stance': 'SUPPORT', 'responds_to': None}
        with self.assertRaises(ProviderBlocked):
            self.provider(lambda body, duration: response_fixture(payload)).predict(self.context, self.character, stage='RESPONSE')

    def test_reused_response_id_cannot_count_as_new_execution(self):
        provider = self.provider()
        provider.predict(self.context, self.character)
        with self.assertRaises(ProviderBlocked) as error:
            provider.predict(self.context, self.character)
        self.assertEqual(error.exception.code, 'DUPLICATE_EXECUTION_ID')

    def test_predraw_analysis_can_explicitly_skip_tickets(self):
        for runner in self.context['runners']:
            runner['horse_no'] = None
        payload = output_fixture()
        payload.update(tickets=[], skip_reason='枠順・馬番未確定')
        result = self.provider(lambda body, duration: response_fixture(payload)).predict(self.context, self.character)
        self.assertTrue(validate_execution(result))

    def test_stage_binding_and_persistence_time(self):
        payload = output_fixture()
        payload['change_reason'] = 'SYNTHETIC: prior evidence remains unchanged'
        result = self.provider(lambda body, duration: response_fixture(payload)).predict(self.context, self.character, stage='FINAL')
        result['persisted_at'] = result['output']['saved_at']
        self.assertTrue(validate_execution(result))
        result['persisted_at'] = '2026-11-12T00:01:00+00:00'
        with self.assertRaises(ValueError):
            validate_execution(result)

    def test_final_requires_reason_even_when_forecast_retained(self):
        with self.assertRaises(ProviderBlocked):
            self.provider().predict(self.context, self.character, stage='FINAL')

    def test_frame_tickets_keep_separate_numbers_and_same_frame_requires_two_horses(self):
        for runner in self.context['runners']:
            runner['frame_no'] = 2
        payload = output_fixture()
        payload['tickets'] = [{'type': 'FRAME_QUINELLA', 'frame_nos': [2, 2], 'stake_yen': 100}]
        result = self.provider(lambda body, duration: response_fixture(payload)).predict(self.context, self.character)
        self.assertTrue(validate_execution(result))
        self.context['runners'][1]['frame_no'] = 3
        with self.assertRaises(ProviderBlocked):
            self.provider(lambda body, duration: response_fixture(payload)).predict(self.context, self.character)
        payload['tickets'][0] = {'type': 'FRAME_QUINELLA', 'horse_nos': [1, 2], 'stake_yen': 100}
        with self.assertRaises(ProviderBlocked):
            self.provider(lambda body, duration: response_fixture(payload)).predict(self.context, self.character)


if __name__ == '__main__':
    unittest.main()
