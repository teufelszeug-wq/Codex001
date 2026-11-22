import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm, unlink, writeFile } from 'node:fs/promises';
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
  const { initial, final, roundtable } = await runForecastPanel(options);
  const v1 = join(output, card.race_id, 'v1.json');
  const original = await readFile(v1, 'utf8');
  assert.equal(initial.records.length, 19);
  assert.equal(final.records.length, 19);
  assert.equal(final.previous_sha256, initial.content_sha256);
  assert.deepEqual(final.metadata.review.topics.map(topic => topic.id), ['DIAGNOSIS', 'COURSE', 'INFORMATION', 'CASE', 'BETS']);
  assert.equal(final.metadata.review.facilitator.name, '篠宮 律');
  assert.equal(final.metadata.publication_window, 'PRE_DAY');
  assert.equal(roundtable.topics[0].turns[0].name, '篠宮 律');
  assert.deepEqual(roundtable.topics[0].turns.filter(turn => turn.speaker_id === 'RIO-REPORTER-01')
    .map(turn => turn.horse_no), [1, 2, 3]);
  assert.ok(roundtable.topics.find(topic => topic.id === 'CASE').turns.some(turn => turn.kind === 'REBUTTAL'));
  assert.equal(final.metadata.post_roundtable.length, 19);
  assert.ok(final.records.every(row => Date.parse(roundtable.recorded_at) <= Date.parse(row.execution.started_at)));
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
  const dialoguePath = join(output, card.race_id, 'roundtable-v1.json');
  const dialogue = await readFile(dialoguePath, 'utf8');
  await writeFile(dialoguePath, dialogue.replace('枠順の内から', '改変した本文'));
  await assert.rejects(runForecastPanel(options), /roundtable does not match/);
  await writeFile(dialoguePath, dialogue);
  await writeFile(v1, original.replace('架空馬1', '改ざん馬'));
  await assert.rejects(runForecastPanel(options), /content hash mismatch/);
});

test('isolates provider inputs, preserves v1 when v2 fails, and resumes from saved v1', async t => {
  const output = await directory(t);
  const card = fixture();
  let request = 0;
  let failFinal = true;
  const finalCalls = new Map();
  const model = async input => {
    if (input.review) {
      finalCalls.set(input.agent.id, (finalCalls.get(input.agent.id) ?? 0) + 1);
      assert.equal(input.review.length, 5);
      assert.equal(input.initial.forecaster_id, input.agent.id);
      assert.equal(input.roundtable.topics.length, 5);
      if (failFinal && input.agent.id === 'HONSHI') throw new Error('provider unavailable');
    } else {
      assert.equal(input.initial, null);
      assert.equal(input.review, null);
      assert.equal(input.roundtable, null);
    }
    return { horse_nos: input.eligible.slice(0, 2), reason: '架空のAPI応答',
      response_id: `test-response-${++request}`, model: 'test-model' };
  };
  const now = clock();
  const options = { rawRacecard: card, directory: output, now, model, modelIdentity: 'openai:test-model' };
  await assert.rejects(runForecastPanel(options), /HONSHI: provider unavailable/);
  const v1 = join(output, card.race_id, 'v1.json');
  const original = await readFile(v1, 'utf8');
  const transcript = join(output, card.race_id, 'roundtable-v1.json');
  const savedDialogue = await readFile(transcript, 'utf8');
  await assert.rejects(readFile(join(output, card.race_id, 'v2.json')), { code: 'ENOENT' });
  failFinal = false;
  const { final } = await runForecastPanel(options);
  assert.equal(await readFile(v1, 'utf8'), original);
  assert.equal(await readFile(transcript, 'utf8'), savedDialogue);
  assert.equal(final.records.filter(row => row.execution.provider === 'openai').length, 19);
  assert.equal(new Set(final.records.map(row => row.execution.response_id)).size, 19);
  assert.equal(finalCalls.get('HONSHI'), 2);
  assert.ok([...finalCalls].every(([id, count]) => count === (id === 'HONSHI' ? 2 : 1)));
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
      output: [{ type: 'message', content: [{ type: 'output_text', text: '{"diagnoses":[],"horse_nos":[2],"reason":"架空","skip_reason":null}' }] }],
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
  assert.deepEqual(result, { diagnoses: [], horse_nos: [2], reason: '架空', skip_reason: null,
    contract: 'prism.model_assessment/v2', response_id: 'resp_fixture', model: 'test-model', attempts: 1, usage: null });
});

test('prepares declarations with horse IDs and carries the early record forward when numbers are assigned', async t => {
  const output = await directory(t);
  const card = fixture();
  const early = { ...card, entry_stage: 'DECLARATIONS', runners: card.runners.map(horse => ({
    ...horse, horse_id: String(2022100000 + horse.horse_no), horse_no: null, frame_no: null,
  })) };
  const { declarations, roundtable } = await runForecastPanel({ rawRacecard: early, directory: output, now: clock() });
  assert.equal(declarations.records.length, 19);
  assert.ok(declarations.runners.every(horse => horse.horse_no === null && horse.frame_no === null));
  assert.ok(declarations.records.every(row => row.tickets.length === 0 &&
    row.picks.every(pick => pick.horse_no === null && pick.horse_id)));
  assert.equal(roundtable.topics[0].turns.filter(turn => turn.speaker_id === 'RIO-REPORTER-01' && turn.horse_id).length, 3);
  assert.ok(!roundtable.topics[0].turns.some(turn => turn.horse_no));
  const replay = await runForecastPanel({ rawRacecard: early, directory: output, now: () => card.off_at });
  assert.equal(replay.declarations.content_sha256, declarations.content_sha256);
  let tick = Date.parse('2026-11-13T20:00:00+09:00');
  const later = { ...card, captured_at: '2026-11-13T19:30:00+09:00' };
  const { initial, final } = await runForecastPanel({
    rawRacecard: later, directory: output, now: () => new Date(tick++).toISOString(),
  });
  assert.equal(initial.metadata.declarations_sha256, declarations.content_sha256);
  assert.ok(final.records.some(row => row.tickets.length));
});

test('race-day revision keeps the prior edition and removes scratched horses from every ticket', async t => {
  const output = await directory(t);
  const card = fixture();
  const { final } = await runForecastPanel({ rawRacecard: card, directory: output, now: clock() });
  const day = structuredClone(card);
  day.captured_at = '2026-11-15T12:30:00+09:00';
  day.runners[0].status = 'SCRATCHED';
  day.runners[1].win_odds = 8;
  day.runners[1].body_weight = 492;
  day.track_condition = '稍重';
  day.runners[1].jockey_name = '別の架空騎手';
  const replayClock = () => {
    let ms = Date.parse('2026-11-15T13:00:00+09:00');
    return () => new Date(ms++).toISOString();
  };
  const options = { rawRacecard: day, directory: output, now: replayClock(), updateFrom: 2 };
  const { final: revised } = await runForecastPanel(options);
  assert.equal(revised.version, 3);
  assert.equal(revised.previous_sha256, final.content_sha256);
  assert.equal(revised.metadata.original_final_sha256, final.content_sha256);
  assert.deepEqual(revised.metadata.changes.scratched, [1]);
  assert.deepEqual(revised.metadata.changes.odds, [{ horse_no: 2, from: 10, to: 8 }]);
  assert.deepEqual(revised.metadata.changes.body_weight, [{ horse_no: 2, from: null, to: 492 }]);
  assert.deepEqual(revised.metadata.changes.track_condition, { from: null, to: '稍重' });
  assert.equal(revised.metadata.changes.jockey[0].to, '別の架空騎手');
  assert.ok(revised.records.every(row => row.diagnoses.every(horse => horse.horse_no !== 1) &&
    row.tickets.every(ticket => !ticket.horse_nos.includes(1))));
  assert.equal((await runForecastPanel(options)).final.content_sha256, revised.content_sha256);
  const stored = JSON.parse(await readFile(join(output, card.race_id, 'v2.json')));
  assert.equal(stored.content_sha256, final.content_sha256);
  await unlink(join(output, card.race_id, 'v3.json'));
  await assert.rejects(runForecastPanel({ ...options, now: () => day.off_at }), /pre-race window/);
});

test('model assesses every runner from source facts and may reverse the local ranking', async t => {
  const output = await directory(t);
  let requests = 0;
  const api = makeOpenAiForecaster({ apiKey: 'fixture', model: 'test-model', now: () => BASE_TIME,
    request: async (_, options) => {
      const body = JSON.parse(options.body);
      const data = JSON.parse(body.input);
      assert.equal(data.horses.length, 3);
      assert.equal(data.horses[0].history.length, 2);
      assert.equal(data.forecaster_id === 'HONSHI', data.method === 'editorial');
      assert.equal(data.horses.some(horse => horse.horse_no === 4), false);
      assert.equal(body.text.format.schema.properties.diagnoses.items.additionalProperties, false);
      const response = {
        diagnoses: data.horses.map(horse => ({ horse_no: horse.horse_no, horse_name: horse.horse_name,
          score: data.research_required ? null : horse.horse_no * 10,
          reason: data.research_required ? '専門資料が不足しています。' : '掲載された過去走を担当分野で比較。',
          source_refs: data.research_required ? [] : [data.official_source] })),
        horse_nos: data.research_required ? [] : [3, 2, 1],
        reason: '全頭を比較して判断。', skip_reason: data.research_required ? '専門資料不足のため見送り。' : null,
      };
      return new Response(JSON.stringify({ id: 'response-'+(++requests), status: 'completed', model: 'test-model',
        usage: { input_tokens: 500, output_tokens: 200 },
        output: [{ type: 'message', content: [{ type: 'output_text', text: JSON.stringify(response) }] }] }));
    } });
  const { initial, final } = await runForecastPanel({ rawRacecard: fixture(), directory: output,
    now: clock(), model: api, modelIdentity: 'openai:test-model' });
  assert.equal(requests, 38);
  assert.equal(final.records[0].picks[0].horse_no, 3);
  assert.equal(final.records[0].diagnoses[0].score, 10);
  assert.equal(final.records[0].execution.assessment_contract, 'prism.model_assessment/v2');
  assert.deepEqual(final.records[0].execution.usage, { input_tokens: 500, output_tokens: 200 });
  assert.equal(initial.records.filter(row => row.tickets.length === 0).length, 6);
  assert.equal(final.records.filter(row => row.tickets.length === 0).length, 6);
});

test('rejects missing, renamed and unsupported model diagnoses before publication', async t => {
  const output = await directory(t);
  const model = async input => ({ contract: 'prism.model_assessment/v2',
    diagnoses: input.card.active_runners.map(horse => ({ horse_no: horse.horse_no, horse_name: horse.horse_name,
      score: 80, reason: '出典不一致の架空評価', source_refs: ['https://example.test/unprovided'] })),
    horse_nos: [1], reason: '架空', skip_reason: null, response_id: 'fixture', model: 'test-model' });
  model.contract = 'prism.model_assessment/v2';
  await assert.rejects(runForecastPanel({ rawRacecard: fixture(), directory: output,
    now: clock(), model, modelIdentity: 'openai:test-model' }), /unsupported model diagnosis/);
  await assert.rejects(readFile(join(output, fixture().race_id, 'v1.json')), { code: 'ENOENT' });
});

test('provider retries temporary HTTP failures and honors Retry-After without crossing the deadline', async () => {
  const input = { offAt: new Date(BASE_TIME + 60_000).toISOString(),
    agent: { id: 'fixture', name: '架空担当', specialty: '架空' }, card: fixture(), diagnoses: [] };
  let now = BASE_TIME;
  let calls = 0;
  const delays = [];
  const create = retryAfter => makeOpenAiForecaster({ apiKey: 'fixture', model: 'test-model',
    now: () => now, random: () => 0, sleep: async ms => { delays.push(ms); now += ms; },
    request: async () => {
      calls++;
      if (calls === 1) return new Response('', { status: 429, headers: { 'retry-after': retryAfter } });
      return new Response(JSON.stringify({ id: 'retried', model: 'test-model', status: 'completed',
        output: [{ type: 'message', content: [{ type: 'output_text',
          text: '{"diagnoses":[],"horse_nos":[],"reason":"架空","skip_reason":"不足"}' }] }] }));
    } });
  const decision = await create('2')(input);
  assert.equal(decision.attempts, 2);
  assert.deepEqual(delays, [2000]);
  now = BASE_TIME;
  calls = 0;
  await assert.rejects(create('60')(input), /deadline prevents/);
  assert.equal(calls, 1);
  const forbidden = makeOpenAiForecaster({ apiKey: 'fixture', model: 'test-model', now: () => BASE_TIME,
    request: async () => new Response('', { status: 401 }) });
  await assert.rejects(forbidden(input), /HTTP 401/);
});
