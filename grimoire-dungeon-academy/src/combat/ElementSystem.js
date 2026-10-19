export const Elements = Object.freeze({ ARCANE:'arcane', FIRE:'fire', ICE:'ice', LIGHTNING:'lightning', WIND:'wind', LIGHT:'light', DARK:'dark', ASTRAL:'astral', TIME:'time' });
const MODS = {
  slime: { fire:1.35, lightning:1.15, dark:1.0, light:1.0, arcane:1.0 },
  skeleton: { light:1.6, fire:1.1, dark:0.65, arcane:1.0 }
};
export function elementMultiplier(element, targetType) { return MODS[targetType]?.[element] ?? 1; }
