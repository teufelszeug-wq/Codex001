import { commitPreRaceEdition } from './prediction_edition_commit.mjs';
import { createEditionWriter, readEdition } from './atomic_edition_store.mjs';

// Integration boundary: validate, commit immutably, then verify persisted bytes.
export async function publishPreRaceEdition(records, { directory, now } = {}) {
  if (typeof directory !== 'string' || !directory.trim()) return { saved: false, errors: ['missing_directory'] };
  const result = await commitPreRaceEdition(records, { writeAtomic: createEditionWriter(directory), now });
  if (!result.saved) return result;
  try {
    const persisted = await readEdition(result.receipt.path);
    if (persisted.sha256 !== result.receipt.sha256 ||
        JSON.stringify(persisted.document.records) !== JSON.stringify(records)) {
      return { saved: false, errors: ['persisted_content_mismatch'], receipt: result.receipt };
    }
    return { ...result, verified: true };
  } catch (error) {
    return { saved: false, errors: ['readback_failed'], detail: String(error?.message ?? error), receipt: result.receipt };
  }
}
