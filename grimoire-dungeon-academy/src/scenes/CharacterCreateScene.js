const Phaser = globalThis.Phaser;
import { GameState } from '../core/GameState.js';
export class CharacterCreateScene extends Phaser.Scene {
  constructor(){ super('CharacterCreate'); }
  create(){
    this.add.text(240,120,'入学者登録',{fontFamily:'Noto Sans JP',fontSize:'28px',color:'#fff1b8'}).setOrigin(.5);
    this.add.image(240,240,'hero-idle').setScale(1.5).setOrigin(.5);
    this.add.text(240,330,'名前を入力するか、プリセットを選択',{fontFamily:'Noto Sans JP',fontSize:'14px',color:'#cbd1eb'}).setOrigin(.5);
    const input=document.createElement('input'); input.className='gda-name-input'; input.maxLength=12; input.placeholder='名前'; input.value='ノア';
    const dom=this.add.dom(240,390,input);
    const presets=['ノア','ユナ','ミコト','アリア'];
    presets.forEach((name,i)=>{ const x=105+i*90; const b=this.add.rectangle(x,470,80,42,0x26305a).setStrokeStyle(1,0xc7a85b).setInteractive(); this.add.text(x,470,name,{fontFamily:'Noto Sans JP',fontSize:'14px'}).setOrigin(.5); b.on('pointerdown',()=>input.value=name); });
    const start=this.add.rectangle(240,560,260,58,0x443661).setStrokeStyle(2,0xc7a85b).setInteractive(); this.add.text(240,560,'DUNGEONへ',{fontFamily:'Noto Sans JP',fontSize:'20px',color:'#fff'}).setOrigin(.5); start.on('pointerdown',async()=>{ const name=input.value.trim() || 'ノア';await document.fonts.load('14px "Noto Sans JP"',name); dom.destroy(); this.scene.start('Game',{state:new GameState({name})}); });
  }
}
