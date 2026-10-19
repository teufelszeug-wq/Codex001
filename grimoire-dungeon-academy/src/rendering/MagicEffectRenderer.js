export class MagicEffectRenderer {
  constructor(scene) { this.scene=scene; }
  burst(x,y,color) {
    const g=this.scene.add.graphics().setDepth(20); g.lineStyle(2,color,1); g.strokeCircle(x,y,5); g.strokeCircle(x,y,10);
    this.scene.tweens.add({ targets:g, alpha:0, scale:1.8, duration:220, onComplete:()=>g.destroy() });
  }
}
