export class PixelRenderer {
  constructor(scene) { this.scene=scene; }
  texture(key,w,h,draw) {
    if (this.scene.textures.exists(key)) this.scene.textures.remove(key);
    const g=this.scene.make.graphics({x:0,y:0,add:false});
    draw(g); g.generateTexture(key,w,h); g.destroy(); return key;
  }
  px(g,x,y,w,h,color,alpha=1) { g.fillStyle(color,alpha); g.fillRect(Math.round(x),Math.round(y),w,h); }
}
