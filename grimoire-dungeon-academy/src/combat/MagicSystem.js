import { elementMultiplier } from './ElementSystem.js';
export class MagicSystem {
  cast(state, grimoire, enemy) {
    if (state.mp < grimoire.mpCost) return { ok:false, reason:'mp' };
    state.mp -= grimoire.mpCost;
    const variance = 0.9 + Math.random()*0.2;
    const mult = elementMultiplier(grimoire.element, enemy.type);
    const raw = (state.matk + grimoire.power - enemy.mdef) * variance * mult;
    const crit = Math.random() < state.crit;
    const damage = Math.max(1, Math.floor(raw * (crit ? 1.5 : 1)));
    enemy.hp -= damage;
    return { ok:true, damage, crit, mult };
  }
}
