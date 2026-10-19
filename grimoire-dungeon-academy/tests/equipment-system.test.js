import test from 'node:test';
import assert from 'node:assert/strict';
import { GameState } from '../src/core/GameState.js';
import { EquipmentSystem } from '../src/items/EquipmentSystem.js';

test('cycles through owned grimoires', () => {
  const s = new GameState({ grimoires:['dark','fire','light'], equippedGrimoire:'dark' });
  const eq = new EquipmentSystem(s);
  assert.equal(eq.cycleGrimoire().id, 'fire');
  assert.equal(eq.cycleGrimoire().id, 'light');
  assert.equal(eq.cycleGrimoire().id, 'dark');
});
