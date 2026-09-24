import {openSeries} from './engine.mjs';
import {readWorldCandidate} from './world-candidates.mjs';
import {approveTransaction,recoverTransaction} from './transactions.mjs';
export function worldCandidateAction(root,input){
  if(input?.series_id!==openSeries(root).config.series_id)throw Error('作品IDが一致しません。');
  if(!['approve','apply','rollback'].includes(input.action)||input.confirmed!==true)throw Error('実行する操作と確認が必要です。');
  const r=readWorldCandidate(root,input.id);
  if(input.digest!==r.digest)throw Error('確認した候補と内容が違います。読み直してください。');
  const approval={actor:input.actor,source:input.source,expected_digest:r.digest};
  if(input.action!=='apply'&&(!approval.actor?.trim()||!approval.source?.trim()))throw Error('操作する方の名前と根拠を入力してください。');
  if(input.action==='approve'){
    if(['approved','applied'].includes(r.status)){
      if(r.approval.actor!==approval.actor||r.approval.source!==approval.source)throw Error('保存済みの承認根拠と異なります。');
      return r;
    }
    if(r.status!=='proposed'||r.stale||!r.current_matches_before)throw Error('候補の状態または基準版が変わっています。');
  }else if(input.action==='apply'){
    if(!['approved','applied'].includes(r.status))throw Error('承認済みの候補を指定してください。中断中の処理は先に確認してください。');
    if(r.status==='approved'&&(r.stale||!r.current_matches_before))throw Error('承認後に正本が変わっています。');
  }else{
    if(!['applied','rolled_back'].includes(r.status))throw Error('反映済みの候補を指定してください。');
    if(r.status==='applied'&&!r.current_matches_after)throw Error('後の変更があるため取り消せません。');
    if(r.status==='rolled_back'&&(r.rollback.actor!==approval.actor||r.rollback.source!==approval.source))throw Error('保存済みの取消根拠と異なります。');
  }
  try{
    if(input.action==='approve')approveTransaction(root,r.id,approval);
    else recoverTransaction(root,r.id,input.action==='apply'?'finish':'rollback',approval);
    return readWorldCandidate(root,r.id);
  }catch{
    const e=Error('処理結果の確認が必要です。再送せず、候補を読み直して中断や競合を確認してください。');e.uncertain=true;throw e;
  }
}
