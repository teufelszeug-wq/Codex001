import fs from 'node:fs';
import {openSeries,inside,fingerprint} from './engine.mjs';

const statuses=new Map([
  ['draft','draft'],['approved','approved'],['planned','planned'],
  ['今回の統合改稿・初稿','draft'],['統合改稿C・初稿','draft']
]);
// Read-only accounting. Missing text never implies an unwritten scene.
export function progress(root){
  const {config,state}=openSeries(root),revision=fingerprint(root);
  const chapters=new Map(),unclassified=[],seenFiles=new Set(),seenScenes=new Set();
  for(const scene of state.scene_log){
    const match=/^([A-Z]+)(\d+)-/.exec(scene.id??'');
    const branch=scene.branch??match?.[1],chapter=scene.chapter_id??match?.[2];
    if(!branch||chapter===undefined){unclassified.push({id:scene.id,reason:'branch_or_chapter_unknown'});continue;}
    const key=branch+':'+String(chapter);
    if(!chapters.has(key))chapters.set(key,{branch,chapter:String(chapter),active:branch===state.active_branch,
      approved_chars:0,draft_chars:0,unknown_status_chars:0,scenes:[],missing_text:[],planned:[],excluded:[]});
    const group=chapters.get(key);
    if(scene.superseded_by||scene.current_revision===false){group.excluded.push(scene.id);continue;}
    const logical=key+':'+(scene.logical_scene_id??scene.id);
    if(seenScenes.has(logical))throw Error('multiple current revisions for '+logical);
    seenScenes.add(logical);
    const status=statuses.get(scene.status)??'unknown';
    if(!scene.path){(status==='planned'?group.planned:group.missing_text).push(scene.id);continue;}
    const file=inside(root,scene.path),dir=inside(root,config.manuscript_dir);
    const real=fs.realpathSync(file),base=fs.realpathSync(dir);
    if(!real.startsWith(base+ (process.platform==='win32'?'\\':'/')))throw Error('text outside manuscript directory');
    if(seenFiles.has(real))throw Error('same manuscript file counted twice');
    seenFiles.add(real);
    const content=fs.readFileSync(real,'utf8');
    const chars=[...content.replace(/\r\n|\r|\n/g,'')].length;
    if(status==='planned')throw Error('planned scene has manuscript; classify its status first');
    group[status==='unknown'?'unknown_status_chars':status+'_chars']+=chars;
    group.scenes.push({id:scene.id,status,original_status:scene.status,path:scene.path,chars});
  }
  if(fingerprint(root)!==revision)throw Error('series changed during progress report');
  for(const group of chapters.values()){
    const target=group.active&&Number(group.chapter)===state.chapter?.number?state.chapter:null;
    group.minimum_target_chars=target?.minimum_target_chars??null;
    group.standard_target_chars=target?.standard_target_chars??null;
    group.current_text_chars=group.approved_chars+group.draft_chars;
    group.approved_remaining_to_minimum=Number.isFinite(group.minimum_target_chars)?Math.max(0,group.minimum_target_chars-group.approved_chars):null;
    group.chapter_complete=false; // Length is never evidence of editorial completion.
  }
  return {series_id:config.series_id,revision,counting:'Unicode code points excluding line breaks; includes headings, spaces and Markdown',
    chapters:[...chapters.values()],unclassified,
    note:'Only registered manuscripts are counted. Missing source text is not the same as unwritten. Explicit planned scenes do not prove the chapter plan is exhaustive. No automatic approval.'};
}
