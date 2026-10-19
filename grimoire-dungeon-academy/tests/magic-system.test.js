import test from 'node:test';
import assert from 'node:assert/strict';
import { GameState } from '../src/core/GameState.js';
import { MagicSystem } from '../src/combat/MagicSystem.js';
import { getGrimoire } from '../src/items/GrimoireDatabase.js';

test('casting consumes MP and damages enemy', () => {
  const state = new GameState({ mp:20, matk:7 });
  const enemy = { type:'slime', hp:20, mdef:1 };
  const grimoire = getGrimoire('fire');
  const before = state.mp;
  const r = new MagicSystem().cast(state, grimoire, enemy);
  assert.equal(r.ok, true);
  assert.equal(state.mp, before - grimoire.mpCost);
  assert.ok(enemy.hp < 20);
});
