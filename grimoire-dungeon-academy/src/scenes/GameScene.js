const Phaser = globalThis.Phaser;
const ROT = globalThis.ROT;
import { DungeonGenerator } from '../dungeon/DungeonGenerator.js';
import { FOVSystem } from '../dungeon/FOVSystem.js';
import { getFloorTheme } from '../dungeon/FloorTheme.js';
import { Player } from '../entities/Player.js';
import { Enemy } from '../entities/Enemy.js';
import { EquipmentSystem } from '../items/EquipmentSystem.js';
import { CombatSystem } from '../combat/CombatSystem.js';
import { MagicSystem } from '../combat/MagicSystem.js';
import { SaveManager } from '../core/SaveManager.js';
import { TurnManager } from '../core/TurnManager.js';
import { CharacterRenderer } from '../rendering/CharacterRenderer.js';
import { MagicEffectRenderer } from '../rendering/MagicEffectRenderer.js';
import { HUD } from '../ui/HUD.js';
import { MessageLog } from '../ui/MessageLog.js';
import { MobileControls } from '../ui/MobileControls.js';

const TILE=24;
export class GameScene extends Phaser.Scene {
  constructor(){ super('Game'); }
  init(data){ this.state=data.state; this.loaded=Boolean(data.loaded); }
  create(){
    this.generator=new DungeonGenerator(40,32); this.equipment=new EquipmentSystem(this.state); this.combat=new CombatSystem(); this.magic=new MagicSystem();
    this.charRenderer=new CharacterRenderer(this); this.charRenderer.generateHeroTextures(this.state.robe,this.state.equippedGrimoire); this.effects=new MagicEffectRenderer(this); this.buildFloor();
    this.mapGraphics=this.add.graphics().setDepth(0); this.enemySprites=new Map();
    this.hero=this.add.sprite(this.player.x*TILE+TILE/2,this.player.y*TILE+TILE/2,'hero-idle','0').setScale(0.5).setOrigin(0.5,0.78).setDepth(10);
    this.cameras.main.setBounds(0,0,40*TILE,32*TILE+160); this.cameras.main.startFollow(this.hero,true,0.18,0.18,0,-120);
    this.hud=new HUD(this,this.state); this.log=new MessageLog(this,14,590,452); this.controls=new MobileControls(this,{move:(dx,dy)=>this.actMove(dx,dy),cast:()=>this.actCast(),book:()=>this.cycleBook(),save:()=>this.saveGame()});
    this.turns=new TurnManager(()=>this.enemyTurn()); this.bindKeys(); this.log.push(`B${this.state.floor}F ${getFloorTheme(this.state.floor).name}へ降りた。`); this.redraw();
  }
  buildFloor(){
    const data=this.generator.generate(this.state.seed,this.state.floor); this.tiles=data.tiles; this.stairs=data.stairs; const sx=this.loaded && Number.isInteger(this.state.playerX) ? this.state.playerX : data.start.x; const sy=this.loaded && Number.isInteger(this.state.playerY) ? this.state.playerY : data.start.y; this.player=new Player(this.state,sx,sy); this.loaded=false; this.enemies=data.enemies.map(e=>new Enemy(e.type,e.x,e.y)); this.fov=new FOVSystem(this.tiles); this.visible=this.fov.compute(this.player.x,this.player.y);
  }
  bindKeys(){
    this.input.keyboard.on('keydown',e=>{ const k=e.key.toLowerCase(); if(k==='arrowup'||k==='w')this.actMove(0,-1); else if(k==='arrowdown'||k==='s')this.actMove(0,1); else if(k==='arrowleft'||k==='a')this.actMove(-1,0); else if(k==='arrowright'||k==='d')this.actMove(1,0); else if(k===' '||k==='enter')this.actCast(); else if(k==='q')this.cycleBook(); else if(k==='p')this.saveGame(); });
  }
  enemyAt(x,y){ return this.enemies.find(e=>e.alive&&e.x===x&&e.y===y); }
  actMove(dx,dy){
    this.turns.run(async()=>{
      const nx=this.player.x+dx, ny=this.player.y+dy; const enemy=this.enemyAt(nx,ny);
      if(enemy){ const r=this.combat.physicalAttack(this.state,enemy); this.log.push(r.hit?`${enemy.name}に杖打ち ${r.damage}。`:'攻撃は外れた。'); this.onEnemyMaybeDefeated(enemy); return true; }
      if(!this.player.move(dx,dy,this.tiles)) return false;
      if(this.player.x===this.stairs.x&&this.player.y===this.stairs.y){ this.nextFloor(); return false; }
      this.visible=this.fov.compute(this.player.x,this.player.y); this.updateHeroTexture(); this.redraw(); return true;
    });
  }
  actCast(){
    this.turns.run(async()=>{
      const candidates=this.enemies.filter(e=>e.alive&&this.visible.has(`${e.x},${e.y}`)).sort((a,b)=>this.dist(a)-this.dist(b)); const target=candidates[0];
      if(!target){ this.log.push('視界内に対象がいない。'); return false; }
      const g=this.equipment.currentGrimoire(); const r=this.magic.cast(this.state,g,target);
      if(!r.ok){ this.log.push('MPが足りない。'); return false; }
      await this.playHeroMotion('castprep'); await this.playHeroMotion('cast');
      this.effects.burst(target.x*TILE+TILE/2,target.y*TILE+TILE/2,g.color); await this.playHeroMotion('release');
      this.log.push(`${g.spell}! ${target.name}に${r.damage}ダメージ${r.mult>1.2?' [弱点]':''}${r.crit?' CRIT!':''}`); this.onEnemyMaybeDefeated(target); this.updateHeroTexture(); this.redraw(); return true;
    });
  }
  dist(e){ return Math.abs(e.x-this.player.x)+Math.abs(e.y-this.player.y); }
  onEnemyMaybeDefeated(enemy){ if(enemy.hp<=0){ this.log.push(`${enemy.name}を倒した。EXP +${enemy.exp}`); if(this.state.gainExp(enemy.exp))this.log.push(`LEVEL UP! Lv.${this.state.level}`); } }
  async enemyTurn(){
    for(const e of this.enemies.filter(x=>x.alive)){
      if(this.state.hp<=0) break;
      const d=this.dist(e); if(d===1){ const r=this.combat.enemyAttack(e,this.state); this.log.push(r.hit?`${e.name}の攻撃 ${r.damage}ダメージ。`:`${e.name}の攻撃を回避。`); continue; }
      if(d>10) continue;
      const path=[]; const pass=(x,y)=>x>=0&&y>=0&&y<this.tiles.length&&x<this.tiles[0].length&&this.tiles[y][x]===0 && !this.enemyAt(x,y);
      const astar=new ROT.Path.AStar(this.player.x,this.player.y,pass,{topology:4}); astar.compute(e.x,e.y,(x,y)=>path.push([x,y]));
      if(path.length>1){ const [nx,ny]=path[1]; if(!(nx===this.player.x&&ny===this.player.y)){ e.x=nx;e.y=ny; } }
    }
    if(this.state.hp<=0){ this.log.push('倒れてしまった……タイトルへ戻る。'); SaveManager.clear(); this.time.delayedCall(800,()=>this.scene.start('Title')); return; }
    this.visible=this.fov.compute(this.player.x,this.player.y); this.redraw();
  }
  cycleBook(){ const g=this.equipment.cycleGrimoire(); this.charRenderer.generateHeroTextures(this.state.robe,g.id); this.log.push(`装備変更：${g.name}`); this.updateHeroTexture(); this.hud.update(); }
  playHeroMotion(name){ return new Promise(resolve=>{ const key=`hero:${name}`; if(!this.anims.exists(key)){ resolve(); return; } this.hero.once('animationcomplete',()=>resolve()); this.hero.play(key,true); }); }
  updateHeroTexture(){ this.hero.stop(); this.hero.setPosition(this.player.x*TILE+TILE/2,this.player.y*TILE+TILE/2); this.hero.setTexture(`hero-walk-${this.player.direction}`,String(this.player.walkFrame)); }
  nextFloor(){ this.state.floor+=1; this.state.playerX=null; this.state.playerY=null; this.state.hp=Math.min(this.state.maxHP,this.state.hp+4); this.state.mp=Math.min(this.state.maxMP,this.state.mp+6); this.buildFloor(); this.hero.setPosition(this.player.x*TILE+TILE/2,this.player.y*TILE+TILE/2); this.log.push(`B${this.state.floor}F ${getFloorTheme(this.state.floor).name}へ。`); this.redraw(); this.saveGame(false); }
  saveGame(show=true){ this.state.playerX=this.player.x; this.state.playerY=this.player.y; SaveManager.save(this.state); if(show)this.log.push('セーブしました。'); }
  redraw(){
    if(!this.mapGraphics)return; const theme=getFloorTheme(this.state.floor); this.mapGraphics.clear();
    for(let y=0;y<this.tiles.length;y++)for(let x=0;x<this.tiles[y].length;x++){ const key=`${x},${y}`, vis=this.visible.has(key), explored=this.fov.explored.has(key); if(!explored)continue; const wall=this.tiles[y][x]===1; const dim = c => { const r=(c>>16)&255,g=(c>>8)&255,b=c&255; return ((r*0.45)<<16)|((g*0.45)<<8)|(b*0.45); }; const color=vis?(wall?theme.wall:theme.floor):(wall?theme.wallDark:dim(theme.floor)); this.mapGraphics.fillStyle(color,1); this.mapGraphics.fillRect(x*TILE,y*TILE,TILE,TILE); if(vis&&!wall&&((x+y+this.state.floor)%17===0)){this.mapGraphics.fillStyle(theme.accent,.22);this.mapGraphics.fillRect(x*TILE+6,y*TILE+6,12,2);} }
    if(this.fov.explored.has(`${this.stairs.x},${this.stairs.y}`)){ const stairAlpha=this.visible.has(`${this.stairs.x},${this.stairs.y}`)?1:0.4; this.mapGraphics.fillStyle(theme.accent,stairAlpha); this.mapGraphics.fillRect(this.stairs.x*TILE+5,this.stairs.y*TILE+5,14,14); this.mapGraphics.lineStyle(2,0x0a0a0a,stairAlpha); this.mapGraphics.strokeRect(this.stairs.x*TILE+5,this.stairs.y*TILE+5,14,14); }
    for(const s of this.enemySprites.values())s.destroy(); this.enemySprites.clear();
    for(const e of this.enemies.filter(x=>x.alive)){ if(!this.visible.has(`${e.x},${e.y}`))continue; const sp=this.add.sprite(e.x*TILE+12,e.y*TILE+12,`enemy-${e.type}`).setDepth(9); this.enemySprites.set(e,sp); }
    if(this.hero){ this.updateHeroTexture(); this.hud?.update(); }
  }
}
