#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { readFile, readdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import { verifyForecastRecord } from '../src/operations/forecast_history.mjs';
import { verifyDeclarations, verifyRacecard } from '../src/operations/forecast_panel.mjs';
import { loadForecastRoster } from '../src/operations/specialist_forecasts.mjs';
import { validateRoundtable } from '../src/operations/roundtable.mjs';

const digest = value => createHash('sha256').update(JSON.stringify(value)).digest('hex');
const read = path => readFile(path, 'utf8').then(JSON.parse);

async function main() {
  const { values: options } = parseArgs({ options: {
    history: { type: 'string' }, race: { type: 'string' }, out: { type: 'string' },
  } });
  if (!options.history || !/^\d{8}-(JRA|NAR)-[A-Z]+-\d{2}$/.test(options.race ?? '') || !options.out) {
    throw new Error('usage: export_newspaper_inputs.mjs --history DIR --race RACE_ID --out FILE');
  }
  const directory = join(options.history, options.race);
  const files = await readdir(directory);
  const roster = await loadForecastRoster();
  const early = !files.includes('racecard.json');
  let cardPath = join(directory, early ? 'declarations-racecard.json' : 'racecard.json');
  let card = await read(cardPath);
  if (card.race_id !== options.race) throw new Error('paper racecard identity mismatch');
  let initial, forecast;
  const versions = files.filter(name => /^v\d+\.json$/.test(name))
    .map(name => Number(name.slice(1, -5))).sort((a, b) => a - b);
  if (early) {
    initial = forecast = verifyDeclarations(await read(join(directory, 'declarations-v1.json')), options.race);
  } else {
    if (!versions.length || versions[0] !== 1 || versions.some((v, i) => v !== i + 1)) throw new Error('paper forecast version chain missing');
    let previous;
    for (const version of versions) {
      const value = verifyForecastRecord(await read(join(directory, `v${version}.json`)), options.race, version);
      if (previous && (value.previous_sha256 !== previous.content_sha256 || Date.parse(value.saved_at) <= Date.parse(previous.saved_at))) {
        throw new Error('paper forecast revision chain mismatch');
      }
      if (version === 1) initial = value;
      previous = value;
    }
    forecast = previous;
  }
  if (forecast.metadata?.source_sha256 && forecast.metadata.source_sha256 !== card.source_sha256) {
    let match = false;
    for (const name of files.filter(name => /^(?:v\d+-racecard|racecard-v\d+)\.json$/.test(name))) {
      const candidate = await read(join(directory, name));
      if (candidate.source_sha256 === forecast.metadata.source_sha256) {
        card = candidate; cardPath = join(directory, name); match = true; break;
      }
    }
    if (!match) throw new Error('paper latest forecast racecard original missing');
  }
  if (card.race_id !== options.race) throw new Error('paper latest racecard identity mismatch');
  const normalized = verifyRacecard(card);
  if (!Number.isFinite(Date.parse(forecast.saved_at)) || Date.parse(forecast.saved_at) >= Date.parse(card.off_at)) throw new Error('paper forecast was not saved before off');
  const roundtable = validateRoundtable(await read(join(directory,
    early ? 'declarations-roundtable-v1.json' : 'roundtable-v1.json')), initial, roster);
  if (forecast.metadata?.roundtable_sha256 && forecast.metadata.roundtable_sha256 !== digest(roundtable)) {
    throw new Error('paper final forecast and roundtable mismatch');
  }
  const runners = normalized.active_runners;
  const identity = row => early ? row.horse_id : row.horse_no;
  const expectedHorses = new Map(runners.map(row => [identity(row), row.horse_name]));
  const expectedAgents = new Map(roster.forecasters.map(row => [row.id, row]));
  const records = forecast.records;
  if (records.length !== expectedAgents.size || new Set(records.map(row => row.forecaster_id)).size !== records.length) throw new Error('paper forecaster coverage mismatch');
  const executions = [];
  const executionIds = new Set();
  const responseIds = new Set();
  for (const record of records) {
    const agent = expectedAgents.get(record.forecaster_id);
    if (!agent || agent.name !== record.display_name || !record.execution_id || executionIds.has(record.execution_id) ||
        record.diagnoses.length !== runners.length || new Set(record.diagnoses.map(identity)).size !== runners.length ||
        !record.diagnoses.every(row => expectedHorses.get(identity(row)) === row.horse_name && typeof row.reason === 'string' && row.reason.trim()) ||
        !record.picks.every(row => expectedHorses.get(identity(row)) === row.horse_name) ||
        (!record.picks.length && !record.skip_reason) || !Array.isArray(record.tickets) ||
        record.tickets.some(ticket => ticket.stake_yen !== 100)) throw new Error(`paper original incomplete: ${record.forecaster_id}`);
    const api = record.execution?.provider === 'openai' && typeof record.execution.response_id === 'string' && !!record.execution.response_id.trim();
    executionIds.add(record.execution_id);
    if (record.execution?.provider === 'openai' && (!api || responseIds.has(record.execution.response_id))) throw new Error('paper API execution proof missing or duplicated');
    if (api) responseIds.add(record.execution.response_id);
    executions.push({ forecaster_id: agent.id, name: agent.name, execution_id: record.execution_id,
      provider: record.execution?.provider ?? 'unknown', response_id: record.execution?.response_id ?? null,
      independent_ai_verified: api,
      label: api ? '独立API実行記録あり' : record.execution?.provider === 'local_rules'
        ? '独立AI未実行・担当別ルール計算' : '独立AI実行未確認',
      prediction_present: record.picks.length > 0, pass_reason: record.skip_reason ?? null });
  }
  const payload = { schema: 'prism.newspaper_inputs/v1', race_id: options.race,
    exported_at: new Date().toISOString(), card, forecast, roundtable, executions,
    scope: early ? 'DECLARATIONS_PREVIEW' : executions.every(row => row.independent_ai_verified) ? 'RECORDED_API_FORECASTS' : 'EDITORIAL_PROVISIONAL',
    original_forecast_sha256: forecast.content_sha256,
    source_paths: { card: cardPath,
      forecast: join(directory, early ? 'declarations-v1.json' : `v${forecast.version}.json`),
      roundtable: join(directory, early ? 'declarations-roundtable-v1.json' : 'roundtable-v1.json') } };
  await writeFile(options.out, JSON.stringify(payload, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ race_id: options.race, runners: runners.length, records: records.length,
    independent_api: executions.filter(row => row.independent_ai_verified).length, topics: roundtable.topics.length }));
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
