// RIO→PRISM recovery adapter. Read-only, fail-closed; never promotes historical evidence.
export function normalizeRecovery(manifests) {
  const records=[], seen=new Set(), conflicts=[];
  for (const manifest of manifests) for (const r of (manifest.records ?? [])) {
    if (!r.race_id || !r.source || !r.version || !r.forecaster_id) { conflicts.push({reason:"missing_identity",record:r}); continue; }
    const key=[r.race_id,r.forecaster_id,r.version,r.source_id ?? r.source].join("|");
    if (seen.has(key)) continue;
    seen.add(key);
    const post=/POST_RACE|RETROSPECTIVE/.test(r.evidence_class ?? "");
    const status=post?"post_race_reconstruction":/PRE_OFF/.test(r.evidence_class ?? "")?"pre_off_unverified":"unclassified";
    const tickets=(r.tickets ?? []).map(t=>({...t,stake_yen:t.stake_yen ?? null}));
    for (const t of tickets) if (!Number.isInteger(t.stake_yen) || t.stake_yen<100 || t.stake_yen%100!==0) conflicts.push({reason:"invalid_stake",key,ticket:t});
    records.push({race_id:r.race_id,race_name:r.race_name??null,horse_names:r.horse_names??[],forecaster_id:r.forecaster_id,source:r.source,source_id:r.source_id??null,saved_at:r.saved_at??null,version:r.version,evidence_class:r.evidence_class??null,temporal_class:status,live_eligible:false,marks:r.marks??{},tickets,missing:r.missing??[],original:r});
  }
  return {schema:"prism.recovery.adapter/v1",records,conflicts,summary:{records:records.length,pre_off_unverified:records.filter(x=>x.temporal_class==="pre_off_unverified").length,post_race_reconstruction:records.filter(x=>x.temporal_class==="post_race_reconstruction").length,live_eligible:0}};
}
