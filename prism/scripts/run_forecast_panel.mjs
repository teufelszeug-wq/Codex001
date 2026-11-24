#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import { makeOpenAiForecaster } from '../src/operations/openai_forecaster.mjs';
import { runForecastPanel, verifyRacecard } from '../src/operations/forecast_panel.mjs';
import { diagnoseSpecialist, loadForecastRoster, validateSupplementalEvidence } from '../src/operations/specialist_forecasts.mjs';
import { buildForecasterReadiness, FORECAST_CONTRACT_SHA256, FORECAST_CONTRACT_VERSION,
  getForecasterContract } from '../src/operations/forecaster_contracts.mjs';

function runtime() {
  const required = ['OPENAI_API_KEY', 'PRISM_OPENAI_MODEL'];
  const missing = required.filter(name => !process.env[name]?.trim());
  return { ready: missing.length === 0, missing,
    model: process.env.PRISM_OPENAI_MODEL || null, provider_requests: 0 };
}

async function main() {
  const { values: options } = parseArgs({ options: {
    card: { type: 'string' },
    evidence: { type: 'string' },
    out: { type: 'string' },
    model: { type: 'string', default: 'local' },
    'check-runtime': { type: 'boolean', default: false },
    'check-agents': { type: 'boolean', default: false },
    'update-from': { type: 'string' },
  } });
  if (options['check-runtime']) {
    const state = runtime();
    console.log(JSON.stringify(state, null, 2));
    process.exitCode = state.ready ? 0 : 2;
    return;
  }
  if (options['check-agents']) {
    if (options.evidence && !options.card) throw new Error('--evidence requires --card');
    const roster = await loadForecastRoster();
    const card = options.card ? verifyRacecard(JSON.parse(await readFile(options.card, 'utf8'))) : null;
    const evidence = options.evidence ? JSON.parse(await readFile(options.evidence, 'utf8')) : [];
    const asOf = new Date().toISOString();
    if (card) validateSupplementalEvidence(evidence, card, asOf);
    console.log(JSON.stringify({
      schema: 'prism.forecaster_readiness/v1', checked_at: asOf,
      contract_version: FORECAST_CONTRACT_VERSION, contract_sha256: FORECAST_CONTRACT_SHA256,
      purpose: '役割定義と入力不足の診断。予想実行・学習性能・本番完成の証明ではない。',
      provider_requests: 0, runtime: runtime(),
      race_id: card?.race_id ?? null,
      pre_race_window: card ? Date.parse(card.captured_at) <= Date.parse(asOf) && Date.parse(asOf) < Date.parse(card.off_at) : null,
      facilitator: { ...roster.facilitator, participates_in_forecasts: false },
      forecasters: roster.forecasters.map(agent => ({
        forecaster_id: agent.id, name: agent.name, method: agent.method,
        profile_status: agent.profile_status ?? null,
        role_contract: getForecasterContract(agent),
        input_readiness: card ? buildForecasterReadiness({ agent, card,
          diagnoses: diagnoseSpecialist({ agent, card, evidence }) }) : { state: 'NOT_CHECKED', reason: '出馬表未指定。' },
      })),
    }, null, 2));
    return;
  }
  if (!options.card || !options.out || !['local', 'openai'].includes(options.model)) {
    throw new Error('usage: node prism/scripts/run_forecast_panel.mjs --card CARD.json --out DIRECTORY [--evidence EVIDENCE.json] [--model local|openai] [--update-from VERSION]');
  }
  const rawRacecard = JSON.parse(await readFile(options.card, 'utf8'));
  const evidence = options.evidence ? JSON.parse(await readFile(options.evidence, 'utf8')) : [];
  const modelName = process.env.PRISM_OPENAI_MODEL;
  const model = options.model === 'openai' ? makeOpenAiForecaster({ apiKey: process.env.OPENAI_API_KEY, model: modelName }) : undefined;
  const { declarations, final, roundtable } = await runForecastPanel({
    rawRacecard, evidence, directory: options.out, model,
    modelIdentity: model ? `openai:${modelName}` : 'local_rules',
    updateFrom: options['update-from'] === undefined ? undefined : Number(options['update-from']),
  });
  const forecast = declarations ?? final;
  const summaries = forecast.records.map(record => ({
    forecaster_id: record.forecaster_id, name: record.display_name, specialty: record.specialty, execution_id: record.execution_id,
    top_pick: record.picks[0] ?? null, tickets: record.tickets,
    skip_reason: record.skip_reason,
    role_contract_version: record.role_contract?.version ?? null,
    decision_status: record.decision_status ?? null, input_readiness: record.input_readiness ?? null,
    provider: record.execution.provider, response_id: record.execution.response_id ?? null,
  }));
  console.log(JSON.stringify({
    race_id: forecast.race_id, race_name: forecast.race_name, off_at: forecast.off_at, saved_at: forecast.saved_at,
    version: final?.version ?? null, publication_window: final?.metadata.publication_window ?? 'DECLARATIONS',
    phase: final?.metadata.phase ?? 'DECLARATIONS',
    changes: final?.metadata.changes ?? null,
    model_backend: final?.metadata.model_backend ?? declarations.model_backend,
    api_records: forecast.records.filter(record => record.execution.provider === 'openai').length,
    local_records: forecast.records.filter(record => record.execution.provider === 'local_rules').length,
    review_topics: roundtable?.topics.length ?? final?.metadata.review.topics.length ?? 0,
    roundtable: roundtable ? {
      mode: roundtable.mode, recorded_at: roundtable.recorded_at,
      turns: roundtable.topics.reduce((total, topic) => total + topic.turns.length, 0),
    } : null,
    runners: forecast.runners.length, forecasts: summaries,
    history: join(options.out, forecast.race_id),
  }, null, 2));
}
main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
