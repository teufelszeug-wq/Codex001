const TYPES = {
  slime: { name:'スライム', hp:9, atk:3, def:1, mdef:1, exp:5, color:0x5ac8a8 },
  skeleton: { name:'スケルトン', hp:13, atk:4, def:2, mdef:2, exp:7, color:0xd8d0bd }
};
export class Enemy {
  constructor(type,x,y) { Object.assign(this, TYPES[type] ?? TYPES.slime); this.type=type; this.maxHP=this.hp; this.x=x; this.y=y; }
  get alive() { return this.hp>0; }
}
