// Contract boundary for Python prediction engine output -> immutable PRISM records.
// Never invent timestamps, provenance, or predictor identities.
export function adaptPythonPredictions(payload) {
  if (!payload || typeof payload !== 'object' || !Array.isArray(payload.predictions) || !payload.predictions.length)
    throw new Error('missing_predictions');
  const fields = ['race_id','scheduled_start_at','saved_at','version','source'];
  for (const field of fields) if (typeof payload[field] !== 'string' || !payload[field].trim()) throw new Error('missing:' + field);
  const seen = new Set();
  return payload.predictions.map((prediction, index) => {
    if (!prediction || typeof prediction !== 'object') throw new Error('invalid_prediction:' + index);
    for (const field of ['horse_name','predictor_id'])
      if (typeof prediction[field] !== 'string' || !prediction[field].trim()) throw new Error('missing:' + field + ':' + index);
    const key = JSON.stringify([prediction.predictor_id, prediction.horse_name]);
    if (seen.has(key)) throw new Error('duplicate_prediction:' + index);
    seen.add(key);
    if (prediction.result_known === true) throw new Error('result_leak:' + index);
    if (prediction.source_observed_at !== undefined && (typeof prediction.source_observed_at !== 'string' || !prediction.source_observed_at.trim()))
      throw new Error('invalid_source_observed_at:' + index);
    return {
      race_id: payload.race_id, scheduled_start_at: payload.scheduled_start_at,
      saved_at: payload.saved_at, version: payload.version, source: payload.source,
      ...(prediction.source_observed_at !== undefined ? {source_observed_at: prediction.source_observed_at} : {}),
      record_type: 'pre_race', horse_name: prediction.horse_name,
      predictor_id: prediction.predictor_id, result_known: false,
      ...(prediction.selection !== undefined ? {selection: prediction.selection} : {})
    };
  });
}
