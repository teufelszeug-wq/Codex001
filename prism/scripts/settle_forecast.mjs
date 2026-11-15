#!/usr/bin/env node
import { readFile, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { parseArgs } from 'node:util';
import { verifyForecastRecord } from '../src/operations/forecast_history.mjs';
import { settleForecast } from '../src/operations/settlement.mjs';

async function declaredRunners(forecast, path) {
  if (forecast.metadata.entry_status) return forecast.metadata.entry_status;
  if (forecast.version === 2) {
    try {
      const initial = verifyForecastRecord(JSON.parse(await readFile(join(dirname(path), 'v1.json'), 'utf8')),
        forecast.race_id, 1);
      if (initial.content_sha256 !== forecast.previous_sha256) throw new Error('initial forecast binding mismatch');
      return initial.metadata?.entry_status ?? forecast.runners;
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
  }
  return forecast.runners;
}

async function main() {
  const { values } = parseArgs({ options: {
    forecast: { type: 'string' }, result: { type: 'string' }, out: { type: 'string' },
  } });
  if (!values.forecast || !values.result || !values.out) {
    throw new Error('usage: node prism/scripts/settle_forecast.mjs --forecast FORECAST.json --result RESULT.json --out SETTLEMENT.json');
  }
  const [forecast, result] = await Promise.all([values.forecast, values.result].map(async path =>
    JSON.parse(await readFile(path, 'utf8'))));
  verifyForecastRecord(forecast, forecast.race_id, forecast.version);
  if (!['FINAL', 'UPDATE'].includes(forecast.metadata?.phase) ||
      !(Date.parse(forecast.saved_at) < Date.parse(forecast.off_at)) ||
      result.schema !== 'prism.official_result/v1' ||
      !/^[a-f0-9]{64}$/.test(result.source_sha256) ||
      !(Date.parse(result.published_at) >= Date.parse(forecast.off_at))) {
    throw new Error('a saved pre-off final forecast and official result are required');
  }
  const source = new URL(result.official_source);
  const jra = ['jra.go.jp', 'www.jra.go.jp'].includes(source.hostname) && source.pathname === '/JRADB/accessS.html';
  const nar = source.hostname === 'www.keiba.go.jp' && source.pathname === '/KeibaWeb/TodayRaceInfo/RaceMarkTable';
  if (source.protocol !== 'https:' || !(jra || nar) || source.username || source.password || source.port) {
    throw new Error('official JRA or NAR result URL required');
  }
  const toNames = rows => new Map(rows.map(horse => [horse.horse_no, horse.horse_name]));
  const expected = toNames(await declaredRunners(forecast, values.forecast));
  const actual = toNames(result.finishers);
  if (expected.size !== actual.size || actual.size !== result.finishers.length ||
      [...expected].some(([number, name]) => actual.get(number) !== name)) {
    throw new Error('official result does not match the forecast runner list');
  }
  const settled = settleForecast({ forecast, result, settled_at: new Date().toISOString() });
  const output = { ...settled, official_result_source_sha256: result.source_sha256,
    forecast_version: forecast.version, forecast_saved_at: forecast.saved_at };
  await writeFile(values.out, JSON.stringify(output, null, 2) + '\n', { flag: 'wx' });
  console.log(JSON.stringify({ race_id: settled.race_id, forecasters: settled.summary.length, output: values.out }));
}
main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
