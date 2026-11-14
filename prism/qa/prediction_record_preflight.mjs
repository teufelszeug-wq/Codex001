// PRISM prediction-record preflight; standalone, no external dependencies.
// Rejects retrospective records masquerading as pre-race predictions.
export function validatePredictionRecord(record) {
  const errors = [];
  const required = ['race_id', 'horse_name', 'predictor_id', 'source', 'saved_at', 'version', 'scheduled_start_at'];
  for (const key of required) if (typeof record?.[key] !== 'string' || !record[key].trim()) errors.push('missing:' + key);
  const parse = (value, key) => {
    if (typeof value !== 'string' || !/^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}(?:\\.\\d+)?(?:Z|[+-]\\d{2}:\\d{2})$/.test(value)) { errors.push('invalid_datetime:' + key); return NaN; }
    const timestamp = Date.parse(value);
    if (!Number.isFinite(timestamp)) errors.push('invalid_datetime:' + key);
    return timestamp;
  };
  const saved = parse(record?.saved_at, 'saved_at');
  const start = parse(record?.scheduled_start_at, 'scheduled_start_at');
  if (Number.isFinite(saved) && Number.isFinite(start) && saved >= start) errors.push('not_pre_race');
  if (!['pre_race', 'retrospective', 'simulation'].includes(record?.record_type)) errors.push('invalid_record_type');
  if (record?.record_type === 'pre_race' && record?.result_known === true) errors.push('result_leak');
  return { valid: errors.length === 0, errors };
}
