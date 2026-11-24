import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { buildForecasterReadiness, getForecasterContract, validateForecasterContracts } from '../../src/operations/forecaster_contracts.mjs';
import { diagnoseSpecialist, forecastSpecialist, loadForecastRoster, validateSupplementalEvidence } from '../../src/operations/specialist_forecasts.mjs';

const load = name => readFile(new URL(`../../data/operations/${name}`, import.meta.url), 'utf8').then(JSON.parse);
const roster = await loadForecastRoster();
const learning = roster.forecasters.find(row => row.id === 'PRISM-LEARNING-01');
const now = () => '2026-11-23T01:00:00+09:00';
const card = {
  official_url: 'https://www.jra.go.jp/JRADB/accessD.html?CNAME=synthetic', race_date: '2026-11-29',
  venue: '東京', course: { surface: 'TURF', distance_m: 2400 },
  active_runners: [1, 2, 3].map(horse_no => ({ horse_no, horse_name: `架空馬${horse_no}`,
    history: [], pedigree: {}, official_rating: 110 - horse_no })),
};
const evidence = [1, 2].map(horse_no => ({ method: 'learning', horse_no, score: 90 - horse_no * 10,
  reason: '合成テスト専用の改善ルール適用資料。実学習成績ではない。',
  source_url: `https://example.com/synthetic-learning/${horse_no}`, available_at: now() }));

test('binds every forecaster to a distinct sourced role and preserves the editor as facilitator', async () => {
  const contracts = await load('forecaster_contracts.json');
  const snapshot = await load('character_roles_20261123.json');
  validateForecasterContracts(roster, contracts);
  assert.equal(contracts.forecasters.length, 19);
  assert.equal(contracts.facilitator.participates_in_forecasts, false);
  for (const agent of roster.forecasters.filter(row => row.id !== 'HONSHI')) {
    const contract = getForecasterContract(agent);
    const original = snapshot.rows.find(row => row.url === contract.canonical_source);
    assert.equal(original['名前'], agent.name);
    assert.equal(original['会議上の役割'], contract.canonical_role);
    assert.equal(original['設定状態'], contract.character_status);
  }
  assert.equal(getForecasterContract(learning).canonical_role, '専門AIの振り返りと学習ルールの監査');
  assert.equal(getForecasterContract(learning).persona.voice, null);
  assert.equal(getForecasterContract(roster.forecasters.find(row => row.method === 'statistics')).persona.voice_status, 'UNCONFIRMED');
  const rio = getForecasterContract(roster.forecasters.find(row => row.method === 'reporter'));
  assert.equal(rio.persona.voice_status, 'SOURCE_CONFIRMED');
  assert.equal(rio.persona.voice.includes('負けず嫌い'), false);
});

test('rejects duplicate, missing, reassigned and incomplete role contracts', async () => {
  const baseline = await load('forecaster_contracts.json');
  for (const corrupt of [
    value => value.forecasters.pop(),
    value => { value.forecasters[0] = value.forecasters[1]; },
    value => { value.forecasters[0].method = 'learning'; },
    value => { value.forecasters[0].display_name = '別の担当'; },
    value => { value.forecasters[0].decision_rule = ''; },
    value => { value.forecasters[0].output_requirements = []; },
    value => { value.facilitator.participates_in_forecasts = true; },
  ]) {
    const value = structuredClone(baseline);
    corrupt(value);
    assert.throws(() => validateForecasterContracts(roster, value), /contract/);
  }
});

test('does not make missing personality settings a gate on sourced forecasting', () => {
  const agent = { ...learning, profile_status: '要照合', personality: null };
  assert.equal(getForecasterContract(agent).forecaster_id, learning.id);
  assert.throws(() => getForecasterContract({ ...agent, name: '別の担当' }), /mismatched/);
});

test('labels missing learning inputs as a reasoned pass, with complete horse-by-horse gaps', async () => {
  const result = await forecastSpecialist({ agent: learning, card, evidence: [], now,
    phase: 'PRELIMINARY', initial: null, review: null });
  assert.equal(result.decision_status, 'PASSED_WITH_REASON');
  assert.equal(result.input_readiness.state, 'MISSING_INPUT');
  assert.equal(result.input_readiness.missing_horses.length, 3);
  assert.equal(result.input_readiness.local_ranking_ready, false);
  assert.equal(result.picks.length, 0);
  assert.equal(result.tickets.length, 0);
  assert.match(result.skip_reason, /予想改善ルール/);
});

test('accepts supported learning evaluations without inventing a score for missing horses', async () => {
  validateSupplementalEvidence(evidence, card, now());
  const result = await forecastSpecialist({ agent: learning, card, evidence, now,
    phase: 'PRELIMINARY', initial: null, review: null });
  assert.equal(result.decision_status, 'PREDICTED');
  assert.equal(result.input_readiness.state, 'PARTIAL_INPUT');
  assert.equal(result.input_readiness.assessed_runners, 2);
  assert.equal(result.input_readiness.missing_horses[0].horse_name, '架空馬3');
  assert.deepEqual(result.picks.map(row => row.horse_no), [1, 2]);
  assert.equal(result.diagnoses[2].score, null);
  assert.equal(result.tickets[0].stake_yen, 100);
  assert.equal(result.execution.provider, 'local_rules');
  assert.equal(result.role_contract.canonical_source, getForecasterContract(learning).canonical_source);
});

test('rejects incomplete or mismatched readiness input instead of overstating coverage', () => {
  const diagnoses = diagnoseSpecialist({ agent: learning, card, evidence });
  assert.throws(() => buildForecasterReadiness({ agent: learning, card, diagnoses: diagnoses.slice(1) }), /complete matching/);
  diagnoses[0].horse_name = '別の馬';
  assert.throws(() => buildForecasterReadiness({ agent: learning, card, diagnoses }), /complete matching/);
});

test('reports all agent contracts and absent runtime configuration without making API calls', () => {
  const script = fileURLToPath(new URL('../../scripts/run_forecast_panel.mjs', import.meta.url));
  const output = spawnSync(process.execPath, [script, '--check-agents'], { encoding: 'utf8',
    env: { ...process.env, OPENAI_API_KEY: '', PRISM_OPENAI_MODEL: '' } });
  assert.equal(output.status, 0, output.stderr);
  const report = JSON.parse(output.stdout);
  assert.equal(report.forecasters.length, 19);
  assert.equal(report.provider_requests, 0);
  assert.deepEqual(report.runtime.missing, ['OPENAI_API_KEY', 'PRISM_OPENAI_MODEL']);
  assert.ok(report.forecasters.every(row => row.input_readiness.state === 'NOT_CHECKED'));
  assert.equal(report.facilitator.participates_in_forecasts, false);
});
