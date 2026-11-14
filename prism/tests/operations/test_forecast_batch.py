from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from run_forecast_batch import prepare, run


class BatchForecastTests(unittest.TestCase):
    def test_keeps_unframed_capture_until_numbered_card_is_available(self):
        early = {'race_id': 'TEST', 'entry_stage': 'DECLARATIONS', 'off_at': '2030-11-14T15:30:00+09:00'}
        numbered = {'race_id': 'TEST', 'off_at': early['off_at']}
        with TemporaryDirectory() as tmp, patch('run_forecast_batch.target', side_effect=[
            ('TEST', lambda: early), ('TEST', lambda: self.fail('unexpected request while resuming')),
            ('TEST', lambda: numbered), ('TEST', lambda: self.fail('unexpected request for frozen card')),
        ]):
            directory = Path(tmp)
            self.assertEqual(prepare(directory, 'url'), ('TEST', early))
            self.assertEqual(prepare(directory, 'url'), ('TEST', early))
            (directory / 'TEST' / 'declarations-roundtable-v1.json').touch()
            self.assertEqual(prepare(directory, 'url'), ('TEST', numbered))
            self.assertEqual(prepare(directory, 'url'), ('TEST', numbered))

    def test_rejects_successful_command_without_forecasts(self):
        card = {'race_name': 'test', 'off_at': '2030-11-14T15:15:00+09:00', 'runners': [{}, {}, {}]}
        response = '{"phase":"FINAL","publication_window":"PRE_DAY","runners":3,"forecasts":[],"roundtable":null,"saved_at":"2030-11-13T11:00:00Z"}'
        with TemporaryDirectory() as tmp, patch('run_forecast_batch.prepare', return_value=('TEST', card)), \
                patch('run_forecast_batch.subprocess.run') as command:
            command.return_value.returncode = 0
            command.return_value.stdout = response
            report = run(Path(tmp), ['official-url'])
        self.assertEqual(report['finalized'], 0)
        self.assertEqual(report['races'], [])
        self.assertEqual(report['errors'][0]['race_id'], 'TEST')
        self.assertIn('no forecaster records', report['errors'][0]['error'])

    def test_batches_in_off_time_order_and_keeps_successes_on_input_failure(self):
        def prepared(_, url):
            if url == 'broken':
                raise ValueError('missing official identity')
            return url, {'race_name': url, 'off_at': '2030-11-14T' + ('06:30:00Z' if url == 'late' else '15:15:00+09:00'), 'runners': [{}, {}, {}]}
        response = '{"phase":"FINAL","publication_window":"PRE_DAY","runners":3,"race_id":"early","forecasts":[{"tickets":[],"execution_id":"run-1"}],"roundtable":null,"saved_at":"2030-11-13T11:00:00Z"}'
        with TemporaryDirectory() as tmp, patch('run_forecast_batch.prepare', side_effect=prepared), \
                patch('run_forecast_batch.subprocess.run') as command:
            command.return_value.returncode = 0
            command.side_effect = [
                type('Result', (), {'returncode': 0, 'stdout': response})(),
                type('Result', (), {'returncode': 0, 'stdout': response.replace('"race_id":"early"', '"race_id":"late"')})(),
            ]
            report = run(Path(tmp), ['late', 'broken', 'early'])
        self.assertEqual([row['race_id'] for row in report['races']], ['early', 'late'])
        self.assertEqual(report['finalized'], 2)
        self.assertEqual(report['errors'], [{'source': 'broken', 'error': 'missing official identity'}])

    def test_rejects_mismatched_race_id_and_post_start_timestamp(self):
        card = {'race_name': 'test', 'off_at': '2030-11-14T15:15:00+09:00', 'runners': [{}]}
        base = {'race_id': 'WRONG', 'phase': 'FINAL', 'publication_window': 'PRE_DAY',
                'runners': 1, 'forecasts': [{'execution_id': 'run-1', 'tickets': []}],
                'roundtable': None, 'saved_at': '2030-11-13T11:00:00Z'}
        import json
        for record, expected in [(base, 'race_id mismatch'),
                                 ({**base, 'race_id': 'TEST', 'saved_at': '2030-11-14T07:00:00Z'}, 'not saved before')]:
            with self.subTest(expected=expected), TemporaryDirectory() as tmp, \
                    patch('run_forecast_batch.prepare', return_value=('TEST', card)), \
                    patch('run_forecast_batch.subprocess.run') as command:
                command.return_value.returncode = 0
                command.return_value.stdout = json.dumps(record)
                report = run(Path(tmp), ['official-url'])
                self.assertEqual(report['finalized'], 0)
                self.assertIn(expected, report['errors'][0]['error'])

    def test_rejects_future_saved_at_and_wrong_phase(self):
        import json
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        future = (now + timedelta(hours=1)).isoformat()
        off = (now + timedelta(days=2)).isoformat()
        past = (now - timedelta(hours=1)).isoformat()
        card = {'race_name': 'test', 'off_at': off, 'runners': [{}]}
        base = {'race_id': 'TEST', 'phase': 'FINAL', 'publication_window': 'PRE_DAY',
                'runners': 1, 'forecasts': [{'execution_id': 'run-1', 'tickets': []}],
                'roundtable': None}
        for record, expected in [
            ({**base, 'saved_at': future}, 'saved_at is in the future'),
            ({**base, 'saved_at': past, 'phase': 'DECLARATIONS'}, 'phase does not match')
        ]:
            with self.subTest(expected=expected), TemporaryDirectory() as tmp, \
                    patch('run_forecast_batch.prepare', return_value=('TEST', card)), \
                    patch('run_forecast_batch.subprocess.run') as command:
                command.return_value.returncode = 0
                command.return_value.stdout = json.dumps(record)
                report = run(Path(tmp), ['official-url'])
                self.assertEqual(report['finalized'], 0)
                self.assertIn(expected, report['errors'][0]['error'])
