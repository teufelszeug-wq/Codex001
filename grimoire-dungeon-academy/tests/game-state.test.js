import test from 'node:test'; import assert from 'node:assert/strict'; import { GameState } from '../src/core/GameState.js';
test('gainExp levels up and restores resources',()=>{ const s=new GameState(); const leveled=s.gainExp(99); assert.equal(leveled,true); assert.ok(s.level>1); assert.equal(s.hp,s.maxHP); assert.equal(s.mp,s.maxMP); });
