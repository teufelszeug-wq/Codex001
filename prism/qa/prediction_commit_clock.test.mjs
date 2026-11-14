import test from 'node:test';
import assert from 'node:assert/strict';
import { commitPreRaceEdition } from './prediction_edition_commit.mjs';

const record = (saved_at) => ({
  race_id: 'TEST-20261115-01', horse_name: 'Fixture Horse',
  predictor_id: 'fixture-ai', source: 'test-fixture',
  saved_at, version: 'eve-v1', record_type: 'pre_race',
  scheduled_start_at: '2026-11-15T15:00:00+09:00',
  source_observed_at: '2026-11-14T09:00:00+09:00',
  result_known: false
});

test('rejects future-dated saved_at even if before race', async () => {
  let writes = 0;
  const result = await commitPreRaceEdition([record('2026-11-15T10:00:00+09:00')], {
    now: () => new Date('2026-11-14T22:00:00+09:00'),
    writeAtomic: async () => { writes++; return { id: 'bad' }; }
  });
  assert.equal(result.saved, false);
  assert.deepEqual(result.errors, ['record_saved_at_in_future']);
  assert.equal(writes, 0);
});

test('allows an earlier saved_at with a pre-start commit clock', async () => {
  const result = await commitPreRaceEdition([record('2026-11-14T20:00:00+09:00')], {
    now: () => new Date('2026-11-14T22:00:00+09:00'),
    writeAtomic: async () => ({ id: 'fixture-receipt' })
  });
  assert.equal(result.saved, true);
});
