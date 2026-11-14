import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const source = readFileSync(new URL('../../src/operations/race_runner.mjs', import.meta.url), 'utf8');

test('pre-off runner validates three timestamps with numeric UTC offsets', () => {
  const correct = String.raw`[+-]\\d{2}:\\d{2}`;
  const broken = String.raw`[+-]\\\\d{2}:\\\\d{2}`;
  assert.equal(source.split(correct).length - 1, 3);
  assert.equal(source.includes(broken), false);
});
