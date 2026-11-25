// Map declaration evidence by official horse ID, never by a supplied provisional number.
export function mapDeclarationEvidence(rows, card, asOf) {
  if (card.entry_stage !== 'DECLARATIONS' || !Array.isArray(rows)) throw new Error('declaration evidence required');
  const cutoff = Date.parse(asOf), off = Date.parse(card.off_at);
  if (!Number.isFinite(cutoff) || !Number.isFinite(off) || cutoff >= off) throw new Error('invalid pre-race cutoff');
  const horses = new Map();
  for (const horse of card.active_runners) {
    if (!/^\d{10}$/.test(horse.horse_id) || horses.has(horse.horse_id)) throw new Error('invalid horse identity');
    horses.set(horse.horse_id, horse);
  }
  const seen = new Set();
  return rows.map(row => {
    const horse = horses.get(row.horse_id);
    const time = Date.parse(row.available_at);
    if (!horse || row.horse_no != null || row.horse_name !== horse.horse_name ||
        typeof row.method !== 'string' || !row.method.trim() ||
        !Number.isFinite(time) || time > cutoff) throw new Error('invalid declaration evidence');
    const key = row.method + ':' + row.horse_id;
    if (seen.has(key)) throw new Error('duplicate declaration evidence');
    seen.add(key);
    return {...row, horse_no: horse.horse_no};
  });
}
