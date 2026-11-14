import { validatePredictionBatch } from './prediction_batch_preflight.mjs';

// Inject a durable, atomic storage function. Never report an edition saved until it succeeds.
export async function commitPreRaceEdition(records, { writeAtomic, now = () => new Date() } = {}) {
  const validation = validatePredictionBatch(records);
  if (!validation.valid) return { saved: false, errors: validation.errors };
  if (records.some(r => r.record_type !== 'pre_race')) return { saved: false, errors: ['not_pre_race_edition'] };
  const current = now();
  if (!(current instanceof Date) || !Number.isFinite(current.getTime())) return { saved: false, errors: ['invalid_commit_clock'] };
  const starts = records.map(r => Date.parse(r.scheduled_start_at));
  if (starts.some(t => !Number.isFinite(t) || current.getTime() >= t)) return { saved: false, errors: ['commit_after_start'] };
  if (typeof writeAtomic !== 'function') return { saved: false, errors: ['missing_atomic_writer'] };
  const snapshot = structuredClone(records);
  try {
    const receipt = await writeAtomic(snapshot);
    if (!receipt || typeof receipt !== 'object' || typeof receipt.id !== 'string' || !receipt.id.trim())
      return { saved: false, errors: ['missing_durable_receipt'] };
    return { saved: true, receipt, count: snapshot.length };
  } catch (error) {
    return { saved: false, errors: ['atomic_write_failed'], detail: String(error?.message ?? error) };
  }
}