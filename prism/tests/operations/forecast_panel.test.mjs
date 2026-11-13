import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { runForecastPanel } from '../../src/operations/forecast_panel.mjs';
import { makeOpenAiForecaster } from '../../src/operations/openai_forecaster.mjs';

const BASE_TIME = Date.parse('2026-11-13T19:00:00+09:00');
function clock() {
  let ms = BASE_TIME;
  return () => new Date(ms++).toISOString();
}
function fixture() {
  return {
    schema: 'prism.official_racecard/v1', authority: 'JRA', race_id: '20261115-JRA-KYOTO-11',
    race_name: '架空競走', race_date: '2026-11-15', venue: '京都', race_no: 11,
    off_at: '2026-11-15T15:40:00+09:00', captured_at: '2026-11-13T18:00:00+09:00',
    official_url: 'https://www.jra.go.jp/JRADB/accessD.html?CNAME=synthetic', source_verified: true,
    source_verification: 'JRA_RACECARD_IDENTITY_MATCH', source_sha256: 'f'.repeat(64),
    course: { surface: 'TURF', distance_m: 2200, direction: 'RIGHT' },
    runners: [1, 2, 3, 4].map(number => ({
      horse_no: number, horse_name: `架空馬${number}`, frame_no: number, jockey_name: '架空騎手',
      status: number === 4 ? 'SCRATCHED' : 'DECLARED', official_rating: 112 - number * 3, win_odds: number * 5,
      pedigree: { sire: '架空の父' },
      history: [{
        date: '2026-10-04', venue: '京都', surface: 'TURF', distance_m: 2200,
        finish: number, field_size: 10, rating: 114 - number * 4,
        last_3f: 34 + number, first_call: number, jockey_name: '架空騎手',
      }, {
        date: '2026-09-15', venue: '京都', surface: 'TURF', distance_m: 2000,
        finish: number + 1, field_size: 12, rating: 110 - number * 3,
        last_3f: 34.5 + number, first_call: number + 1, jockey_name: '架空騎手',
      }],
    })),
  };
}
async function directory(t) {
  const path = await mkdtemp(join(tmpdir(), 'prism-panel-'));
  t.after(() => rm(path, { recursive: true, force: true }));
  return path;
}

test('runs the roster twice and retains an immutable, race-bound preliminary forecast', async t => {
  const output = await directory(t);
  const card = fixture();
  const options = { rawRacecard: card, directory: output, now: clock() };
  const { initial, final } = await runForecastPanel(options);
  const v1 = join(output, card.race_id, 'v1.json');
  const original = await readFile(v1, 'utf8');
  assert.equal(initial.records.length, 19);
  assert.equal(final.records.length, 19);
  assert.equal(final.previous_sha256, initial.content_sha256);
  assert.deepEqual(final.metadata.review.topics.map(topic => topic.id), ['DIAGNOSIS', 'COURSE', 'INFORMATION', 'CASE', 'BETS']);
  assert.equal(final.metadata.review.facilitator.name, '篠宮 律');
  assert.equal(final.metadata.publication_window, 'PRE_DAY');
  assert.equal(final.records.find(row => row.forecaster_id === 'RIO-REPORTER-01').display_name, 'りお');
  assert.equal(final.records.find(row => row.forecaster_id === 'RIO-DATA-01').display_name, '黒川 統司');
  const all = [...initial.records, ...final.records];
  assert.equal(new Set(all.map(row => row.execution_id)).size, 38);
  for (const record of all) {
    assert.deepEqual(record.diagnoses.map(row => row.horse_name), ['架空馬1', '架空馬2', '架空馬3']);
    assert.ok(record.tickets.length || record.skip_reason);
    assert.ok(record.tickets.every(ticket => ticket.stake_yen === 100 && !ticket.horse_nos.includes(4)));
  }
  assert.equal(final.records.find(row => row.forecaster_id === 'PRISM-WORKOUT-01').picks.length, 0);
  const rerun = await runForecastPanel({ ...options, now: () => card.off_at });
  assert.equal(rerun.final.content_sha256, final.content_sha256);
  assert.equal(await readFile(v1, 'utf8'), original);
  await writeFile(v1, original.replace('架空馬1', '改ざん馬'));
  await assert.rejects(runForecastPanel(options), /content hash mismatch/);
});

test('isolates provider inputs, preserves v1 when v2 fails, and resumes from saved v1', async t => {
  const output = await directory(t);
  const card = fixture();
  let request = 0;
  let failFinal = true;
  const model = async input => {
    if (input.review) {
      assert.equal(input.review.length, 5);
      assert.equal(input.initial.forecaster_id, input.agent.id);
      if (failFinal && input.agent.id === 'HONSHI') throw new Error('provider unavailable');
    } else {
      assert.equal(input.initial, null);
      assert.equal(input.review, null);
    }
    return { horse_nos: input.eligible.slice(0, 2), reason: '架空のAPI応答',
      response_id: `test-response-${++request}`, model: 'test-model' };
  };
  const now = clock();
  const options = { rawRacecard: card, directory: output, now, model, modelIdentity: 'openai:test-model' };
  await assert.rejects(runForecastPanel(options), /HONSHI: provider unavailable/);
  const v1 = join(output, card.race_id, 'v1.json');
  const original = await readFile(v1, 'utf8');
  await assert.rejects(readFile(join(output, card.race_id, 'v2.json')), { code: 'ENOENT' });
  failFinal = false;
  const { final } = await runForecastPanel(options);
  assert.equal(await readFile(v1, 'utf8'), original);
  assert.equal(final.records.filter(row => row.execution.provider === 'openai').length, 19);
  assert.equal(new Set(final.records.map(row => row.execution.response_id)).size, 19);
});

test('rejects an unverified card, target-race data, future specialist evidence and off-time writes', async t => {
  const output = await directory(t);
  const card = fixture();
  const options = { rawRacecard: card, directory: output, now: clock() };
  await assert.rejects(runForecastPanel({ ...options, rawRacecard: { ...card, source_verified: false } }), /verified official/);
  const contaminated = structuredClone(card);
  contaminated.runners[0].history[0].date = card.race_date;
  await assert.rejects(runForecastPanel({ ...options, rawRacecard: contaminated }), /prior start/);
  const evidence = [{ method: 'workout', horse_no: 1, score: 80, reason: '架空資料',
    available_at: card.off_at, source_url: 'https://example.com/fixture' }];
  await assert.rejects(runForecastPanel({ ...options, evidence }), /unavailable supplemental/);
  await assert.rejects(runForecastPanel({ ...options, now: () => card.off_at }), /pre-race window/);
  await assert.rejects(readFile(join(output, card.race_id, 'v1.json')), { code: 'ENOENT' });
});

test('creates stateless structured OpenAI calls and uses the provider response ID', async () => {
  const calls = [];
  const request = async (url, options) => {
    calls.push({ url, body: JSON.parse(options.body) });
    return new Response(JSON.stringify({
      id: 'resp_fixture', status: 'completed', model: 'test-model',
      output: [{ type: 'message', content: [{ type: 'output_text', text: '{"horse_nos":[2],"reason":"架空"}' }] }],
    }));
  };
  const predict = makeOpenAiForecaster({ apiKey: 'fixture', model: 'test-model', request });
  const result = await predict({
    offAt: new Date(Date.now() + 60_000).toISOString(),
    agent: { name: '架空担当', specialty: '架空分野' }, card: fixture(),
    diagnoses: [], eligible: [2], review: null, initial: null,
  });
  assert.equal(calls[0].url, 'https://api.openai.com/v1/responses');
  assert.equal(calls[0].body.store, false);
  assert.equal(calls[0].body.text.format.strict, true);
  assert.equal(calls[0].body.previous_response_id, undefined);
  assert.deepEqual(result, { horse_nos: [2], reason: '架空', response_id: 'resp_fixture', model: 'test-model' });
});
