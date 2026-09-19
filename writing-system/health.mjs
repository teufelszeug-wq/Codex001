import fs from 'node:fs';
import {openSeries,validate,fingerprint,inside,atomic,hash} from './engine.mjs';
export function health(root){
  const s=openSeries(root),validation=validate(root),counts={};
  for(const card of s.state.cards) counts[card.type]=(counts[card.type]??0)+1;
  const configured=s.config.roles.filter(role=>s.config.workers?.[role]);
  return {series_id:s.config.series_id,checked_at:new Date().toISOString(),revision:fingerprint(root),
    validation,paused:!s.control.manuscript_generation_enabled,current_scene:s.state.current_scene,
    records:{cards_by_type:counts,scenes:s.state.scene_log.length,manuscripts:validation.counts.length,
      emotional_trajectory:s.state.emotional_trajectory?.length??0,literary_rules:s.state.literary_signature_log?.length??0,
      decisions:s.state.change_log.length,images:s.state.image_assets?.length??0},
    capabilities:{structural_validation:'implemented',council_request_and_collection:'implemented',
      external_workers:{configured_roles:configured,live_connection_verified:false},
      semantic_causality_validation:'editorial_review_required',automatic_canon_update:'not_implemented',
      approved_single_state_change:'implemented',multi_file_transaction:'journaled_with_read_guard',
      map_event_simulation:'not_implemented',automatic_remote_sync:'not_implemented'},
    note:'Record counts and configuration do not prove that a module ran. Live connections require separate evidence.'};
}
export function snapshot(root){
  const s=openSeries(root),report=health(root);
  if(!report.validation.passed) throw Error('cannot export invalid series');
  const paths=[...new Set(['system/series.json',s.config.control,s.config.state,...(s.config.context_files??[]),
    ...['system/world.json','system/sources.json'].filter(p=>fs.existsSync(inside(root,p))),
    ...s.state.scene_log.filter(x=>x.path).map(x=>x.path)])].sort();
  const entries=paths.map(p=>{const content=fs.readFileSync(inside(root,p),'utf8');return {path:p,content,sha256:hash(content)};});
  const bundle={schema_version:1,series_id:s.config.series_id,revision:report.revision,entries};
  if(fingerprint(root)!==report.revision) throw Error('series changed during export');
  const file=inside(root,'system/exports/'+report.revision+'.json');
  if(fs.existsSync(file)){if(fs.readFileSync(file,'utf8')!==JSON.stringify(bundle,null,2)+'\n')throw Error('existing export differs');}
  else atomic(file,bundle);
  return {file,revision:report.revision,files:entries.length,remote_sync:false};
}
