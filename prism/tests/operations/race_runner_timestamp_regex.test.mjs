import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const source = readFileSync(new URL('../../src/operations/race_runner.mjs', import.meta.url), 'utf8');

test('forecast timestamps use numeric UTC offsets, not escaped literal d', () => {
  assert.equal(source.includes(String.raw`[+-]\\\\d{2}:\\\\d{2}`), false);
  assert.equal((source.match(/\[\+\-\]\\d\{2\}:\\d\{2\}/g) ?? []).length, 3);
});
