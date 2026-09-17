const Phaser = globalThis.Phaser;
import { SaveManager } from '../core/SaveManager.js';
export class TitleScene extends Phaser.Scene {
  constructor(){ super('Title'); }
  create(){
    this.cameras.main.setBackgroundColor('#090b15');
    this.add.text(240,170,'GRIMOIRE\nDUNGEON ACADEMY',{fontFamily:'Noto Sans JP',fontSize:'33px',align:'center',color:'#fff1b8',stroke:'#3a2c56',strokeThickness:5}).setOrigin(.5);
    this.add.text(240,265,'グリモア・ダンジョン・アカデミー',{fontFamily:'Noto Sans JP',fontSize:'14px',color:'#c7a85b'}).setOrigin(.5);
    const button=(y,label,cb,enabled=true)=>{ const bg=this.add.rectangle(240,y,280,58,enabled?0x26305a:0x20202a).setStrokeStyle(2,enabled?0xc7a85b:0x555555); const tx=this.add.text(240,y,label,{fontFamily:'Noto Sans JP',fontSize:'20px',color:enabled?'#fff':'#777'}).setOrigin(.5); if(enabled){ bg.setInteractive({useHandCursor:true}).on('pointerdown',cb); tx.setInteractive({useHandCursor:true}).on('pointerdown',cb);} };
    button(390,'NEW GAME',()=>this.scene.start('CharacterCreate'));
    button(470,'CONTINUE',()=>{ const s=SaveManager.load(); if(s?.status==='victory'){this.add.text(240,540,'この記録は実習修了済みです。NEW GAMEへ。',{fontFamily:'Noto Sans JP',fontSize:'13px'}).setOrigin(.5);return;}if(s) this.scene.start('Game',{state:s,loaded:true}); },SaveManager.exists());
    this.add.text(240,610,'魔導書を替えると、属性も魔法も変わる。\n学園地下迷宮を攻略せよ。',{fontFamily:'Noto Sans JP',fontSize:'15px',align:'center',color:'#aeb6d9'}).setOrigin(.5);
  }
}
