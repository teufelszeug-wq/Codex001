import test from 'node:test'; import assert from 'node:assert/strict'; import { elementMultiplier } from '../src/combat/ElementSystem.js';
test('light is strong against skeleton',()=>assert.ok(elementMultiplier('light','skeleton')>1));
test('dark is resisted by skeleton',()=>assert.ok(elementMultiplier('dark','skeleton')<1));
