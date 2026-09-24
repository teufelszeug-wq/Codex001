import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const dir=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(dir);
const names=[];
function collect(relative){for(const entry of fs.readdirSync(path.join(root,relative),{withFileTypes:true})){
  const p=relative+'/'+entry.name;
  if(entry.isSymbolicLink())throw Error('unexpected symlink');
  if(entry.isDirectory()){if(['templates','meetings'].includes(entry.name))collect(p);}
  else if(/\.(mjs|md|json)$/.test(entry.name)||entry.name==='.gitignore')names.push(p);
}}
collect('writing-system');
names.push('writing-system/世界設定の候補.html','writing-system/世界設定の項目入力.html','writing-system/世界設定.html','writing-system/作品一覧.html','writing-system/企画入力.html','writing-system/開発進捗.html','writing-system/research/2026-09-18_旧システム監査.md','amelia/system/control.json','amelia/system/series.json','amelia/system/health.json','amelia/system/validation.json','amelia/state.json','amelia/AGENTS.md');
const requested=process.argv.slice(2);
for(const p of requested)if(!names.includes(p))throw Error('file outside delivery allowlist: '+p);
const files=(requested.length?[...new Set(requested)]:names).sort().map(p=>({path:p,mode:'100644',type:'blob',content:fs.readFileSync(path.join(root,p),'utf8')}));
process.stdout.write(JSON.stringify(files));
