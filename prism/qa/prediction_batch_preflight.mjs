import { validatePredictionRecord } from './prediction_record_preflight.mjs';

// Validate an entire edition before it is accepted as a saved prediction batch.
// A failed batch must not be counted as an issued pre-race edition.
export function validatePredictionBatch(records) {
  if (!Array.isArray(records) || records.length === 0) return { valid: false, errors: ['empty_batch'] };
  const errors = [];
  const seen = new Set();
  const raceIds = new Set();
  const versions = new Set();
  const recordTypes = new Set();
  for (const [index, record] of records.entries()) {
    const result = validatePredictionRecord(record);
    errors.push(...result.errors.map(error => `record[${index}]:${error}`));
    if (record?.race_id) raceIds.add(record.race_id);
    if (record?.version) versions.add(record.version);
    if (record?.record_type) recordTypes.add(record.record_type);
    const key = [record?.race_id, record?.version, record?.record_type, record?.predictor_id, record?.horse_name].map(v => JSON.stringify(v)).join('|');
    if (seen.has(key)) errors.push(`record[${index}]:duplicate_prediction`);
    seen.add(key);
  }
  if (raceIds.size > 1) errors.push('mixed_race_ids');
  if (versions.size > 1) errors.push('mixed_versions');
  if (recordTypes.size > 1) errors.push('mixed_record_types');
  return { valid: errors.length === 0, errors };
}
