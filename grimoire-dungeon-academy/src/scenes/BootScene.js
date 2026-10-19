const Phaser = globalThis.Phaser;
import { CharacterRenderer } from '../rendering/CharacterRenderer.js';
export class BootScene extends Phaser.Scene {
  constructor(){ super('Boot'); }
  create(){ const r=new CharacterRenderer(this); r.generateHeroTextures(); r.generateEnemyTextures(); this.scene.start('Title'); }
}
