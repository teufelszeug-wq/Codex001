// Intentionally tiny, data-only 1px fixes. The algorithm remains the source of truth.
export const HERO_CORRECTIONS = Object.freeze({
  'down:walk:2': [
    { x: 47, y: 39, color: 0xff323646 },
    { x: 48, y: 39, color: 0xff323646 },
  ],
  'down:walk:5': [
    { x: 46, y: 39, color: 0xff323646 },
  ],
});

export function correctionPatch(direction, motion, frame) {
  return HERO_CORRECTIONS[`${direction}:${motion}:${frame}`] || [];
}
