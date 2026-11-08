import { normalizeOfficialRacecard } from './racecard_adapter.mjs';
import { persistInitialForecast } from './forecast_store.mjs';
import { settleForecast } from './settlement.mjs';
const required = (v, name) => { if (typeof v !== 'string' || !v.trim()) throw new Error(name+' required'); return v; };
/** A real provider must supply the racecard and independent model outputs. */
export async function runPreOffRace({ rawRacecard, forecasters, directory, now = () => new Date().toISOString() }) {
  const card = normalizeOfficialRacecard(rawRacecard);
  if (!Array.isArray(forecasters) || !forecasters.length) throw new Error('forecasters required');
  const saved_at = now();
  if (Date.parse(saved_at) >= Date.parse(card.off_at)) throw new Error('race already off');
  const active = card.active_runners.map(({horse_no,horse_name})=>({horse_no,horse_name}));
  const records = [];
  for (const agent of forecasters) {
    required(agent.id,'forecaster id');
    if (typeof agent.predict !== 'function') throw new Error('independent predict function required');
    const output = await agent.predict({ card, as_of:saved_at });
    if (Date.parse(now()) >= Date.parse(card.off_at)) throw new Error('forecast deadline passed during model execution');
    records.push({ ...output, forecaster_id:agent.id, independent_execution:output?.independent_execution===true });
  }
  const final_saved_at = now();
  return persistInitialForecast(directory,{ race_id:card.race_id,race_name:card.race_name,off_at:card.off_at,saved_at:final_saved_at,runners:active,records,source_refs:[card.official_url] });
}
export async function runPostRaceSettlement({ forecast, officialResult, settled_at }) {
  return settleForecast({ forecast, result:officialResult, settled_at });
}
