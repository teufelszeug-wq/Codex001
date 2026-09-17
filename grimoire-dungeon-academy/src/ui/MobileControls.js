export class MobileControls {
  constructor(scene, handlers) {
    const mk=(x,y,label,fn,w=58,h=48)=>{
      const r=scene.add.rectangle(x,y,w,h,0x27325d,0.92).setScrollFactor(0).setDepth(100).setStrokeStyle(1,0xc7a85b).setInteractive({useHandCursor:true});
      const t=scene.add.text(x,y,label,{fontFamily:'monospace',fontSize:'18px',color:'#ffffff'}).setOrigin(.5).setScrollFactor(0).setDepth(101);
      r.on('pointerdown',fn); return [r,t];
    };
    mk(74,720,'←',()=>handlers.move(-1,0)); mk(138,720,'↓',()=>handlers.move(0,1)); mk(202,720,'→',()=>handlers.move(1,0)); mk(138,666,'↑',()=>handlers.move(0,-1));
    mk(330,686,'CAST',handlers.cast,84,48); mk(422,686,'BOOK',handlers.book,84,48); mk(376,744,'SAVE',handlers.save,176,42);
  }
}
