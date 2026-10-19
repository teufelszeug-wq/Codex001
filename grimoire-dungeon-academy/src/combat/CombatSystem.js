export class CombatSystem {
  physicalAttack(attackerState, enemy) {
    const hit = Math.random() <= Math.max(0.55, attackerState.hit - 0.05);
    if (!hit) return { hit:false, damage:0 };
    const crit = Math.random() < attackerState.crit;
    const base = Math.max(1, attackerState.atk - enemy.def + Math.floor(Math.random()*3));
    const damage = crit ? base*2 : base;
    enemy.hp -= damage;
    return { hit:true, crit, damage };
  }
  enemyAttack(enemy, state) {
    if (Math.random() < state.eva) return { hit:false, damage:0 };
    const damage = Math.max(1, enemy.atk - state.def + Math.floor(Math.random()*2));
    state.hp = Math.max(0, state.hp - damage);
    return { hit:true, damage };
  }
}
