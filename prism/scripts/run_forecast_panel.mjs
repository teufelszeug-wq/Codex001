#!/usr/bin/env node
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import { makeOpenAiForecaster } from '../src/operations/openai_forecaster.mjs';
import { runForecastPanel } from '../src/operations/forecast_panel.mjs';

async function main() {
  const { values: options } = parseArgs({ options: {
    card: { type: 'string' },
    evidence: { type: 'string' },
    out: { type: 'string' },
    model: { type: 'string', default: 'local' },
    'update-from': { type: 'string' },
  } });
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
    name: record.display_name, specialty: record.specialty, execution_id: record.execution_id,
    top_pick: record.picks[0] ?? null, tickets: record.tickets,
    skip_reason: record.skip_reason,
  }));
  console.log(JSON.stringify({
    race_id: forecast.race_id, race_name: forecast.race_name, off_at: forecast.off_at, saved_at: forecast.saved_at,
    version: final?.version ?? null, publication_window: final?.metadata.publication_window ?? 'DECLARATIONS',
    phase: final?.metadata.phase ?? 'DECLARATIONS',
    changes: final?.metadata.changes ?? null,
    model_backend: final?.metadata.model_backend ?? declarations.model_backend,
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
