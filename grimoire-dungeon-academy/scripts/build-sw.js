import { readdir,readFile,writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
async function files(dir){const result=[];for(const entry of await readdir(dir,{withFileTypes:true})){const path=`${dir}/${entry.name}`;if(entry.isDirectory())result.push(...await files(path));else if(entry.name!=='service-worker.js')result.push(path);}return result;}
const paths=(await files('dist')).sort();const hash=createHash('sha256');for(const p of paths)hash.update(await readFile(p));const version=hash.digest('hex').slice(0,12);
let sw=await readFile('service-worker.js','utf8');sw=sw.replace('__VERSION__',version).replace('__PRECACHE__',JSON.stringify(['./',...paths.map(p=>'./'+p.slice(5))]));await writeFile('dist/service-worker.js',sw);console.log(`Offline cache ${version}: ${paths.length} files`);
