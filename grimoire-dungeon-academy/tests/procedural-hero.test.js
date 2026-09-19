import test from 'node:test';
import assert from 'node:assert/strict';
import { HeroGenerator } from '../src/rendering/procedural/HeroGenerator.js';
import { PixelSurface } from '../src/rendering/procedural/PixelSurface.js';
import { MOTION_LIBRARY } from '../src/rendering/procedural/HeroMotion.js';

function opaqueCount(surface){let n=0;for(const c of surface.pixels)if((c>>>24)!==0)n++;return n;}

test('PixelSurface primitives stay deterministic',()=>{const s=new PixelSurface(16,16);s.line(0,0,15,15,0xffffffff);s.ellipse(8,8,3,5,0xffff0000);s.polygon([[2,12],[8,2],[14,12]],0xff00ff00);assert.equal(s.pixels.length,256);assert.equal(s.hash(),s.clone().hash());});

test('hero generator creates detailed deterministic 96x96 frame',()=>{const g=new HeroGenerator();const a=g.generate({direction:'down',motion:'idle',element:'dark'});const b=g.generate({direction:'down',motion:'idle',element:'dark'});assert.equal(a.width,96);assert.equal(a.height,96);assert.equal(a.hash(),b.hash());assert.ok(opaqueCount(a)>1700,`opaque pixels ${opaqueCount(a)}`);});

test('walk cycle and directions produce distinct procedural frames',()=>{const g=new HeroGenerator();const hashes=new Set();for(const dir of ['down','left','right','up'])for(let frame=0;frame<6;frame++)hashes.add(g.generate({direction:dir,motion:'walk',frame,element:'dark'}).hash());assert.ok(hashes.size>=20,`expected substantial frame variation, got ${hashes.size}`);});

test('all motion examples generate expected frame counts and variation',()=>{const g=new HeroGenerator();for(const [motion,meta] of Object.entries(MOTION_LIBRARY)){const set=g.generateMotionSet(motion);assert.equal(set.length,meta.frames,motion);assert.ok(set.every(s=>s.width===96&&s.height===96),motion);const hashes=new Set(set.map(s=>s.hash()));if(meta.frames>1&&motion!=='fallen')assert.ok(hashes.size>1,`${motion} lacks variation`);}});

test('hair, outfit, palette and element are data-driven visual differences',()=>{const g=new HeroGenerator();const base=g.generate({motion:'idle'});const bob=g.generate({motion:'idle',hairStyle:'bob'});const robe=g.generate({motion:'idle',outfit:'robe'});const emerald=g.generate({motion:'idle',paletteVariant:'emerald'});const fire=g.generate({motion:'idle',element:'fire'});assert.notEqual(base.hash(),bob.hash());assert.notEqual(base.hash(),robe.hash());assert.notEqual(base.hash(),emerald.hash());assert.notEqual(base.hash(),fire.hash());});

test('weapon type and equipment weight alter generated motion',()=>{const g=new HeroGenerator();const book=g.generate({motion:'idle',weaponType:'grimoire'});const staff=g.generate({motion:'idle',weaponType:'staff'});const light=g.generate({motion:'walk',frame:1,weight:'light'});const heavy=g.generate({motion:'walk',frame:1,weight:'heavy'});assert.notEqual(book.hash(),staff.hash());assert.notEqual(light.hash(),heavy.hash());});

test('casting phases and grimoire element create different frames',()=>{const g=new HeroGenerator();const prep=g.generate({motion:'castprep',frame:2,element:'dark'});const cast=g.generate({motion:'cast',frame:2,element:'dark'});const release=g.generate({motion:'release',frame:1,element:'dark'});const ice=g.generate({motion:'cast',frame:2,element:'ice'});assert.notEqual(prep.hash(),cast.hash());assert.notEqual(cast.hash(),release.hash());assert.notEqual(cast.hash(),ice.hash());});
