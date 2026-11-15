#!/usr/bin/env node
import { createHash } from 'node:crypto';
import { writeFile } from 'node:fs/promises';
import { parseArgs } from 'node:util';
import { verifyForecastRecord } from '../src/operations/forecast_history.mjs';
import { verifyDeclarations } from '../src/operations/forecast_panel.mjs';
import { loadDeclarations, loadForecast, loadRoundtable } from '../src/operations/forecast_store.mjs';
import { formatForecastChanges, formatRoundtable, validateRoundtable } from '../src/operations/roundtable.mjs';
import { loadForecastRoster } from '../src/operations/specialist_forecasts.mjs';

async function main() {
  const { values } = parseArgs({ options: {
    history: { type: 'string' }, race: { type: 'string' }, out: { type: 'string' },
    declarations: { type: 'boolean', default: false },
  } });
  const { history, race, out, declarations } = values;
  if (!history || !race || !out) {
    throw new Error('usage: node prism/scripts/render_roundtable.mjs --history DIRECTORY --race RACE_ID --out ARTICLE.md [--declarations]');
  }
  const initial = declarations ? verifyDeclarations(await loadDeclarations(history, race), race)
    : verifyForecastRecord(await loadForecast(history, race), race, 1);
  const roundtable = validateRoundtable(await loadRoundtable(history, race, { declarations }),
    initial, await loadForecastRoster());
  let article = formatRoundtable(roundtable, initial.race_name);
  if (!declarations) {
    const final = verifyForecastRecord(await loadForecast(history, race, 2), race, 2);
    const digest = createHash('sha256').update(JSON.stringify(roundtable)).digest('hex');
    if (final.previous_sha256 !== initial.content_sha256 || final.metadata.roundtable_sha256 !== digest) {
      throw new Error('final forecast does not match the saved roundtable');
    }
    if (final.metadata.post_roundtable) article += '\n' + formatForecastChanges(final.metadata.post_roundtable);
  }
  await writeFile(out, article, { encoding: 'utf8', flag: 'wx' });
}
main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
