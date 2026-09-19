import { getGrimoire } from './GrimoireDatabase.js';
export class EquipmentSystem {
  constructor(state) { this.state = state; }
  cycleGrimoire(delta=1) {
    const list = this.state.grimoires;
    const i = list.indexOf(this.state.equippedGrimoire);
    this.state.equippedGrimoire = list[(i + delta + list.length) % list.length];
    return getGrimoire(this.state.equippedGrimoire);
  }
  currentGrimoire() { return getGrimoire(this.state.equippedGrimoire); }
}
