import test from 'node:test';
import assert from 'node:assert/strict';
import { forecastSpecialist, loadForecastRoster } from '../../src/operations/specialist_forecasts.mjs';

const now = () => '2026-11-27T00:00:00Z';
const card = {
  entry_stage: 'DECLARATIONS', race_date: '2026-11-29', venue: '東京',
  off_at: '2026-11-29T06:40:00Z', official_url: 'https://example.com/synthetic',
  course: { surface: 'TURF', distance_m: 2400 },
  active_runners: [1, 2].map(n => ({
    horse_no: n, horse_name: '架空馬' + n, official_rating: 120 - n * 10,
    history: [], pedigree: {},
  })),
};
for (const stage of ['DECLARATIONS', 'DRAW_CONFIRMED']) {
  for (const provider of ['local', 'mock']) {
    test(stage + ' / ' + provider + ': ticket safety at specialist boundary', async () => {
      const agent = (await loadForecastRoster()).forecasters.find(a => a.method === 'editorial');
      const model = provider === 'mock' ? async () => ({
        horse_nos: [1], reason: 'synthetic', response_id: 'fixture', model: 'fixture',
      }) : undefined;
      const result = await forecastSpecialist({
        agent, card: { ...card, entry_stage: stage }, evidence: [], now, phase: 'INITIAL', model,
      });
      assert.ok(result.picks.length > 0);
      assert.equal(result.independent_execution, provider === 'mock');
      if (stage === 'DECLARATIONS') {
        assert.deepEqual(result.tickets, []);
        assert.equal(result.stake_yen, 0);
        assert.equal(result.ticket_status, 'NO_BET');
        assert.ok(result.skip_reason);
      } else {
        assert.deepEqual(result.tickets, [{ type: 'WIN', horse_nos: [1], stake_yen: 100 }]);
        assert.equal(result.stake_yen, 100);
      }
    });
  }
}
