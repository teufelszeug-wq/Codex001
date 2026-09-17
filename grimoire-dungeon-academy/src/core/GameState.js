export class GameState {
  constructor(data = {}) {
    this.name = data.name ?? 'ノア';
    this.level = data.level ?? 1;
    this.exp = data.exp ?? 0;
    this.nextExp = data.nextExp ?? 12;
    this.maxHP = data.maxHP ?? 24;
    this.hp = data.hp ?? this.maxHP;
    this.maxMP = data.maxMP ?? 30;
    this.mp = data.mp ?? this.maxMP;
    this.atk = data.atk ?? 2;
    this.matk = data.matk ?? 7;
    this.def = data.def ?? 2;
    this.mdef = data.mdef ?? 4;
    this.hit = data.hit ?? 0.88;
    this.eva = data.eva ?? 0.10;
    this.crit = data.crit ?? 0.08;
    this.floor = data.floor ?? 1;
    this.seed = data.seed ?? Math.floor(Date.now() % 2147483647);
    this.grimoires = data.grimoires ?? ['dark','fire','light'];
    this.equippedGrimoire = data.equippedGrimoire ?? 'dark';
    this.robe = data.robe ?? 'academy';
    this.playerX = data.playerX ?? null;
    this.playerY = data.playerY ?? null;
  }

  gainExp(amount) {
    this.exp += amount;
    let leveled = false;
    while (this.exp >= this.nextExp) {
      this.exp -= this.nextExp;
      this.level += 1;
      this.nextExp = Math.floor(this.nextExp * 1.45 + 4);
      this.maxHP += 4; this.maxMP += 5; this.matk += 2; this.mdef += 1;
      this.hp = this.maxHP; this.mp = this.maxMP;
      leveled = true;
    }
    return leveled;
  }

  serialize() {
    return { ...this };
  }
}
