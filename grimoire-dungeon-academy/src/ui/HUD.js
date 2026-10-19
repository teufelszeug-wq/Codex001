import { getGrimoire } from '../items/GrimoireDatabase.js';
export class HUD {
  constructor(scene,state) {
    this.scene=scene; this.state=state;
    this.panel=scene.add.rectangle(240,52,468,88,0x0d1122,0.94).setScrollFactor(0).setDepth(90).setStrokeStyle(1,0xc7a85b);
    this.text=scene.add.text(14,14,'',{fontFamily:'Noto Sans JP',fontSize:'14px',color:'#fff7d6'}).setScrollFactor(0).setDepth(100);
    this.update();
  }
  update() {
    const g=getGrimoire(this.state.equippedGrimoire);
    this.text.setText(`${this.state.name}  Lv.${this.state.level}   B${this.state.floor}F\nHP ${this.state.hp}/${this.state.maxHP}   MP ${this.state.mp}/${this.state.maxMP}\n魔導書 ${g.name}  [${g.element.toUpperCase()}]  ${g.spell}`);
  }
}
