import crypto from 'node:crypto';

export function stable(value) {
  if (Array.isArray(value)) return '[' + value.map(stable).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(k => JSON.stringify(k)+':'+stable(value[k])).join(',') + '}';
  return JSON.stringify(value);
}
export function sha256(value) { return crypto.createHash('sha256').update(typeof value === 'string' ? value : stable(value)).digest('hex'); }

export class ArtifactCache {
  constructor(){ this.map = new Map(); }
  key(nodeId, raceScope, schemaVersion, codeVersion, upstreamHashes){
    return sha256({nodeId,raceScope,schemaVersion,codeVersion,upstreamHashes:[...upstreamHashes].sort()});
  }
  get(k){ return this.map.get(k); }
  put(k,v){ this.map.set(k,v); }
}

export function runPipeline({raceScope,input,cache=new ArtifactCache(),schemaVersion='0.1',codeVersion='phase-a-v0.1'}){
  const ledger=[];
  const nodes=[
    ['INGEST', x=>({raw:x})],
    ['VALIDATE', x=>{ if(!x.raw?.race_id) throw new Error('race_id required'); return {validated:x.raw}; }],
    ['NORMALIZE', x=>({race_id:x.validated.race_id, authority:x.validated.authority, runners:[...(x.validated.runners??[])].sort((a,b)=>a.horse_no-b.horse_no)})],
    ['FEATURE', x=>({race_id:x.race_id, runner_count:x.runners.length, horse_nos:x.runners.map(r=>r.horse_no)})]
  ];
  let artifact=input; let upstream=[sha256(input)];
  for(const [nodeId,fn] of nodes){
    const key=cache.key(nodeId,raceScope,schemaVersion,codeVersion,upstream);
    const hit=cache.get(key);
    if(hit){ artifact=hit.artifact; upstream=[hit.hash]; ledger.push({node_id:nodeId,decision:'SKIP_CACHE_HIT',status:'SKIPPED',output_hash:hit.hash}); continue; }
    artifact=fn(artifact); const hash=sha256(artifact); cache.put(key,{artifact,hash}); upstream=[hash]; ledger.push({node_id:nodeId,decision:'RUN',status:'SUCCESS',output_hash:hash});
  }
  return {artifact,final_hash:upstream[0],ledger,cache};
}
