import fs from 'node:fs';
import path from 'node:path';
import {inside,read,atomic,hash,openSeries} from './engine.mjs';
function uncertain(){const e=Error('保存結果の照合が必要です。同じ操作を再実行しないでください。');e.uncertain=true;return e;}
// Synchronous operation: record intent before effects; never replay an incomplete write.
export function recordedOperation(root,id,payload,perform){
  if(!/^[a-f0-9-]{36}$/.test(id??''))throw Error('invalid operation id');
  const series_id=openSeries(root).config.series_id;
  const digest=hash(JSON.stringify({series_id,payload}));
  const file=inside(root,'system/operations/'+id+'.json');
  fs.mkdirSync(path.dirname(file),{recursive:true});
  let fd;
  try{fd=fs.openSync(file,'wx');}catch(e){
    if(e.code!=='EEXIST')throw e;
    let old;try{old=read(file);}catch{throw uncertain();}
    if(old.digest!==digest||old.series_id!==series_id)throw Error('同じ操作IDの内容が変わっています。');
    if(old.status!=='completed')throw uncertain();
    return old.result;
  }
  const record={series_id,id,digest,status:'started',started_at:new Date().toISOString()};
  try{fs.writeFileSync(fd,JSON.stringify(record));fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  try{
    const result=perform();
    if(result?.then)throw Error('synchronous operation required');
    atomic(file,{...record,status:'completed',result,completed_at:new Date().toISOString()});
    return result;
  }catch{throw uncertain();}
}
