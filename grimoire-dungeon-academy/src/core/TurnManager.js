export class TurnManager {
  constructor(enemyTurn) { this.enemyTurn = enemyTurn; this.locked = false; }
  async run(playerAction) {
    if (this.locked) return false;
    this.locked = true;
    try {
      const consumed = await playerAction();
      if (consumed) await this.enemyTurn();
      return consumed;
    } finally { this.locked = false; }
  }
}
