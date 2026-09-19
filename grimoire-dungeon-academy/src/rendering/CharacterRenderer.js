import { PixelRenderer } from './PixelRenderer.js';
import { robePalette } from './EquipmentRenderer.js';
import { getGrimoire } from '../items/GrimoireDatabase.js';
import { DEFAULT_HERO_SPEC, cloneHeroSpec } from './procedural/HeroSpec.js';
import { MOTION_LIBRARY } from './procedural/HeroMotion.js';
import { HeroGenerator } from './procedural/HeroGenerator.js';
import { PhaserHeroTextureAdapter } from './procedural/PhaserHeroTextureAdapter.js';

const argb=(rgb)=>(0xff000000|(rgb&0xffffff))>>>0;
const FRAME_RATE={ idle:5, walk:9, castprep:10, cast:10, release:12, dash:12, jump:10, landing:10, damage:12, fallen:4, recovery:9, pickup:8, inspect:6, opendoor:8, sit:4 };

export class CharacterRenderer {
  constructor(scene){this.scene=scene;this.px=new PixelRenderer(scene);this.adapter=new PhaserHeroTextureAdapter(scene);this.heroOptions={};}

  generateHeroTextures(robeId='academy',grimoireId='dark',options={}){
    const robe=robePalette(robeId),grimoire=getGrimoire(grimoireId),spec=cloneHeroSpec(DEFAULT_HERO_SPEC);
    spec.style.uniform=argb(robe.body);spec.style.uniformShadow=argb(robe.shadow);spec.style.gold=argb(robe.trim);spec.style.cape=argb(robe.cape);spec.style.bookRune=argb(grimoire.color);spec.style.bookEdge=argb(grimoire.edge);
    this.heroOptions={hairStyle:'longStraight',outfit:robeId==='astral'?'archmage':robeId==='azure'?'robe':'academy',paletteVariant:'default',weaponType:'grimoire',weight:'medium',...options};
    const generator=new HeroGenerator(spec),common={...this.heroOptions,element:grimoire.element};

    for(const dir of ['down','left','right','up']){
      const frames=generator.generateMotionSet('walk',{...common,direction:dir});
      const textureKey=`hero-walk-${dir}`;this.adapter.uploadAtlas(textureKey,frames);
      this.#registerAnimation(`hero:walk:${dir}`,textureKey,frames.length,FRAME_RATE.walk,true);
    }

    for(const motion of Object.keys(MOTION_LIBRARY).filter(m=>m!=='walk')){
      const frames=generator.generateMotionSet(motion,{...common,direction:'down'});const textureKey=`hero-${motion}`;
      this.adapter.uploadAtlas(textureKey,frames);this.#registerAnimation(`hero:${motion}`,textureKey,frames.length,FRAME_RATE[motion]||8,MOTION_LIBRARY[motion].loop);
    }
    return {generator,options:common};
  }

  #registerAnimation(key,textureKey,count,frameRate,loop){
    if(!this.scene.anims)return;
    if(this.scene.anims.exists?.(key))this.scene.anims.remove(key);
    this.scene.anims.create({key,frames:Array.from({length:count},(_,i)=>({key:textureKey,frame:String(i)})),frameRate,repeat:loop?-1:0});
  }

  generateEnemyTextures(){
    const P=this.px;
    P.texture('enemy-slime',24,24,g=>{P.px(g,4,8,16,11,0x3b8e7a);P.px(g,6,6,12,3,0x5ac8a8);P.px(g,8,11,2,2,0x102020);P.px(g,14,11,2,2,0x102020);P.px(g,5,19,14,2,0x245d52);});
    P.texture('enemy-skeleton',24,24,g=>{P.px(g,6,3,12,10,0xd8d0bd);P.px(g,8,6,2,2,0x24232b);P.px(g,14,6,2,2,0x24232b);P.px(g,10,10,4,1,0x746f67);P.px(g,10,13,4,8,0xb8b2a4);P.px(g,6,15,12,2,0xb8b2a4);});
  }
}
