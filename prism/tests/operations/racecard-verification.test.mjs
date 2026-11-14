import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizeOfficialRacecard, preOffEligibility } from '../../src/operations/racecard_adapter.mjs';

const fixture = () => ({
  authority: 'JRA', race_id: 'TEST-20261114-01', race_name: 'TEST ONLY',
  off_at: '2026-11-14T15:30:00+09:00',
  captured_at: '2026-11-13T20:00:00+09:00',
  official_url: 'https://www.jra.go.jp/',
  runners: [{horse_no: 1, horse_name: 'TEST HORSE', frame_no: 1}],
});

test('unverified input stays unverified', () => {
  const card = normalizeOfficialRacecard(fixture());
  assert.equal(card.source_verified, false);
  assert.equal(card.verification_ref, null);
});
test('verified input retains verification reference', () => {
  const card = normalizeOfficialRacecard({...fixture(), source_verified: true, verification_ref: 'official-snapshot-001'});
  assert.equal(card.source_verified, true);
  assert.equal(card.verification_ref, 'official-snapshot-001');
});
test('verification flag without reference is rejected', () => {
  assert.throws(() => normalizeOfficialRacecard({...fixture(), source_verified: true}), /verification_ref required/);
});
test('after-off captured card is rejected', () => {
  assert.throws(() => normalizeOfficialRacecard({...fixture(), captured_at: '2026-11-14T15:31:00+09:00'}), /captured after scheduled off/);
});
test('off-time boundary rejects same-time forecast save', () => {
  const card = normalizeOfficialRacecard(fixture());
  assert.equal(preOffEligibility(card, '2026-11-14T15:29:59+09:00').eligible, true);
  assert.equal(preOffEligibility(card, '2026-11-14T15:30:00+09:00').eligible, false);
  assert.equal(preOffEligibility(card, '2026-11-14T15:30:01+09:00').eligible, false);
});
