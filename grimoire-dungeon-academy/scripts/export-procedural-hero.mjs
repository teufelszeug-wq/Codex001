import fs from 'node:fs';
import path from 'node:path';
import { HeroGenerator } from '../src/rendering/procedural/HeroGenerator.js';
import { MOTION_LIBRARY } from '../src/rendering/procedural/HeroMotion.js';

const outDir=process.argv[2]||'artifacts/procedural-hero-v2';fs.mkdirSync(outDir,{recursive:true});const gen=new HeroGenerator();
function writePPM(file,surface,bg=[52,55,66]){const header=Buffer.from(`P6\n${surface.width} ${surface.height}\n255\n`);const body=Buffer.alloc(surface.width*surface.height*3);for(let i=0;i<surface.pixels.length;i++){const c=surface.pixels[i]>>>0,a=(c>>>24)&255,o=i*3;if(a===0){body[o]=bg[0];body[o+1]=bg[1];body[o+2]=bg[2];}else{body[o]=(c>>>16)&255;body[o+1]=(c>>>8)&255;body[o+2]=c&255;}}fs.writeFileSync(file,Buffer.concat([header,body]));}
function makeSurface(width,height,bg=0xff343742){return{width,height,pixels:new Uint32Array(width*height).fill(bg)}}
function blit(dst,surf,ox,oy){for(let y=0;y<surf.height;y++)for(let x=0;x<surf.width;x++){const c=surf.pixels[y*surf.width+x]>>>0;if((c>>>24)===0)continue;dst.pixels[(oy+y)*dst.width+ox+x]=c;}}

for(const [motion,meta] of Object.entries(MOTION_LIBRARY)){const frames=gen.generateMotionSet(motion);frames.forEach((s,i)=>writePPM(path.join(outDir,`${motion}-${i}.ppm`),s));}

const motionNames=Object.keys(MOTION_LIBRARY);const motionSheet=makeSurface(96*6,96*motionNames.length);motionNames.forEach((motion,row)=>{const frames=gen.generateMotionSet(motion);for(let col=0;col<6;col++)blit(motionSheet,frames[Math.min(col,frames.length-1)],col*96,row*96);});writePPM(path.join(outDir,'all-motions-sheet.ppm'),motionSheet);

const walkSheet=makeSurface(96*6,96*4);['down','left','right','up'].forEach((dir,row)=>{for(let f=0;f<6;f++)blit(walkSheet,gen.generate({direction:dir,motion:'walk',frame:f}),f*96,row*96);});writePPM(path.join(outDir,'walk-4dir-sheet.ppm'),walkSheet);

const variants=[
  {label:'base',opts:{}},{label:'bob',opts:{hairStyle:'bob'}},{label:'pony',opts:{hairStyle:'ponytail'}},
  {label:'robe',opts:{outfit:'robe'}},{label:'archmage',opts:{outfit:'archmage'}},{label:'emerald',opts:{paletteVariant:'emerald'}},
  {label:'crimson',opts:{paletteVariant:'crimson'}},{label:'ivory',opts:{paletteVariant:'ivory'}},{label:'staff',opts:{weaponType:'staff'}},
  {label:'fire',opts:{element:'fire'}},{label:'ice',opts:{element:'ice'}},{label:'light-heavy',opts:{weight:'heavy'}},
];
const variantSheet=makeSurface(96*6,96*2);variants.forEach((v,i)=>blit(variantSheet,gen.generate({motion:'idle',...v.opts}),(i%6)*96,Math.floor(i/6)*96));writePPM(path.join(outDir,'variant-sheet.ppm'),variantSheet);fs.writeFileSync(path.join(outDir,'variant-labels.json'),JSON.stringify(variants.map(v=>v.label),null,2));
console.log(outDir);
