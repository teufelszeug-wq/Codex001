import crypto from 'node:crypto';
import {openSeries,read,inside,fingerprint} from './engine.mjs';
import {proposeTransaction} from './transactions.mjs';
export const worldCategories=['countries','languages','writing_systems','units','currencies','religions','magic_rules','institutions'];
const statuses=['proposal','confirmed','rejected','unknown'];
const validId=id=>typeof id==='string'&&/^[a-zA-Z][a-zA-Z0-9_-]{0,79}$/.test(id);
// Explicit entries only: free-text plans never become structured canon implicitly.
export function previewWorldEntries(root,input){
  const {config}=openSeries(root),base=fingerprint(root);
  if(input?.series_id!==config.series_id||input.base!==base)throw Error('wrong series or stale world edit');
  if(!Array.isArray(input.entries)||!input.entries.length)throw Error('world entries required');
  const world=read(inside(root,'system/world.json'));
  if(world.series_id!==config.series_id||world.schema_version!==1)throw Error('unsupported world document');
  const next=structuredClone(world),seen=new Set(),diff=[];
  for(const edit of input.entries){
    if(!edit||!worldCategories.includes(edit.category)||!validId(edit.id))throw Error('invalid world category or entry id');
    const key=edit.category+':'+edit.id;if(seen.has(key))throw Error('duplicate world edit');seen.add(key);
    if(typeof edit.value!=='string'||!edit.value.trim()||edit.value.length>10000||!statuses.includes(edit.status))throw Error('world value and status required');
    if(!Array.isArray(edit.sources)||!edit.sources.length||edit.sources.some(s=>typeof s!=='string'||!s.trim()||s.length>4000))throw Error('world entry sources required');
    const entries=next[edit.category];if(!Array.isArray(entries))throw Error('unsupported world category data');
    const ids=new Set();for(const entry of entries){if(!entry||!validId(entry.id)||ids.has(entry.id))throw Error('existing world entries need review');ids.add(entry.id);}
    const index=entries.findIndex(e=>e.id===edit.id),before=index<0?null:structuredClone(entries[index]);
    const after={...before,id:edit.id,value:edit.value,status:edit.status,sources:[...edit.sources]};
    // Decision references are generated when staging; caller-supplied decision IDs are ignored.
    if(before&&['value','status','sources'].every(k=>JSON.stringify(before[k])===JSON.stringify(after[k])))continue;
    if(index<0)entries.push(after);else entries[index]=after;
    diff.push({category:edit.category,id:edit.id,kind:before?'update':'add',before,after});
  }
  if(!diff.length)throw Error('no world changes');
  return {series_id:config.series_id,base,world:next,diff};
}
export function proposeWorldEntries(root,input){
  const preview=previewWorldEntries(root,input),{state,config}=openSeries(root);
  if(typeof input.reason!=='string'||!input.reason.trim())throw Error('world change reason required');
  const nextState=structuredClone(state),decisionId='WORLD-'+crypto.randomUUID();
  for(const change of preview.diff){
    const entry=preview.world[change.category].find(x=>x.id===change.id);entry.decision_id=decisionId;
  }
  nextState.change_log.push({id:decisionId,type:'world_entries',status:'proposed',meeting_id:input.meeting_id,reason:input.reason,
    entries:preview.diff.map(x=>({category:x.category,id:x.id,kind:x.kind})),sources:[...new Set(input.entries.flatMap(x=>x.sources))]});
  const transaction=proposeTransaction(root,[{path:'system/world.json',content:JSON.stringify(preview.world,null,2)+'\n'},{path:config.state,content:JSON.stringify(nextState,null,2)+'\n'}],{reason:input.reason,meeting_id:input.meeting_id,decision_ids:[decisionId]});
  return {transaction,diff:preview.diff,decision_id:decisionId};
}
