const rgba = (hex, a = 0xff) => ((a << 24) | (hex & 0xffffff)) >>> 0;

const BASE_PALETTE = Object.freeze({
  outline: rgba(0x10121a),
  hair: rgba(0x171923),
  hairShadow: rgba(0x0b0d14),
  hairMid: rgba(0x252938),
  hairHighlight: rgba(0x3b4052),
  skin: rgba(0xf4cdb6),
  skinShadow: rgba(0xdda58e),
  blush: rgba(0xe8a8a4),
  eye: rgba(0x363543),
  eyeShadow: rgba(0x1c1d28),
  eyeHighlight: rgba(0x8c8799),
  uniform: rgba(0x24365c),
  uniformShadow: rgba(0x15223d),
  uniformLight: rgba(0x3b507b),
  shirt: rgba(0xe7e0d5),
  ribbon: rgba(0x6a2930),
  ribbonLight: rgba(0x95414b),
  gold: rgba(0xd5a953),
  goldLight: rgba(0xf1d27e),
  cape: rgba(0x202b4b),
  capeShadow: rgba(0x11192d),
  boot: rgba(0x35262d),
  bootLight: rgba(0x6e4935),
  bookCover: rgba(0x4b2d28),
  bookCoverShadow: rgba(0x29191b),
  bookEdge: rgba(0xc79a54),
  bookRune: rgba(0xd9a95a),
  page: rgba(0xe7d7b1),
  magic: rgba(0x9b82d3),
});

export const HAIR_STYLES = Object.freeze(['longStraight', 'bob', 'ponytail']);
export const OUTFIT_STYLES = Object.freeze(['academy', 'robe', 'archmage']);
export const EQUIPMENT_WEIGHTS = Object.freeze(['light', 'medium', 'heavy']);
export const WEAPON_TYPES = Object.freeze(['grimoire', 'staff']);

export const DEFAULT_HERO_SPEC = Object.freeze({
  canvas: { width: 96, height: 96 },
  proportions: {
    centerX: 48,
    groundY: 91,
    headRadiusX: 18,
    headRadiusY: 17,
    torsoWidth: 28,
    torsoHeight: 25,
    legLength: 21,
    armLength: 20,
  },
  handedness: 'left',
  appearance: {
    hairStyle: 'longStraight',
    outfit: 'academy',
    paletteVariant: 'default',
  },
  equipment: {
    weaponType: 'grimoire',
    weight: 'medium',
    grimoireId: 'academy-dark',
  },
  style: BASE_PALETTE,
  grimoire: {
    width: 17,
    height: 21,
    openWidth: 28,
    thickness: 3,
  },
});

export function cloneHeroSpec(spec = DEFAULT_HERO_SPEC) {
  return structuredClone(spec);
}

export function withHeroOptions(spec = DEFAULT_HERO_SPEC, options = {}) {
  const out = cloneHeroSpec(spec);
  if (options.hairStyle) out.appearance.hairStyle = options.hairStyle;
  if (options.outfit) out.appearance.outfit = options.outfit;
  if (options.paletteVariant) out.appearance.paletteVariant = options.paletteVariant;
  if (options.weaponType) out.equipment.weaponType = options.weaponType;
  if (options.weight) out.equipment.weight = options.weight;
  if (options.grimoireId) out.equipment.grimoireId = options.grimoireId;
  return out;
}

export function applyPaletteVariant(spec, variant = 'default') {
  const out = cloneHeroSpec(spec);
  const variants = {
    default: {},
    emerald: {
      uniform: 0x244c45, uniformShadow: 0x16322e, uniformLight: 0x3e6a61,
      cape: 0x203d3a, capeShadow: 0x142824,
    },
    crimson: {
      uniform: 0x552d3c, uniformShadow: 0x351c28, uniformLight: 0x764256,
      cape: 0x462637, capeShadow: 0x2b1823,
    },
    ivory: {
      uniform: 0xc8c2af, uniformShadow: 0x898372, uniformLight: 0xe5dfcf,
      cape: 0xb4ad99, capeShadow: 0x777163, gold: 0x9c7440,
    },
  };
  const selected = variants[variant] || variants.default;
  for (const [key, hex] of Object.entries(selected)) out.style[key] = rgba(hex);
  return out;
}

export function applyElementPalette(spec, element = 'dark') {
  const out = cloneHeroSpec(spec);
  const map = {
    dark:      { cover: 0x4b2d28, shadow: 0x29191b, rune: 0xaa7bc7, magic: 0xa687d6 },
    fire:      { cover: 0x5a2824, shadow: 0x321513, rune: 0xf06b3e, magic: 0xff8b53 },
    ice:       { cover: 0x173946, shadow: 0x0f252d, rune: 0x76d8ef, magic: 0x9ee9f7 },
    lightning: { cover: 0x4a411c, shadow: 0x2b2610, rune: 0xf0d84f, magic: 0xffeb7c },
    light:     { cover: 0x51482d, shadow: 0x302a1b, rune: 0xf0e2a2, magic: 0xfff2bb },
    arcane:    { cover: 0x2a2b50, shadow: 0x191a32, rune: 0x89a0ff, magic: 0xaebcff },
    wind:      { cover: 0x25483f, shadow: 0x173029, rune: 0x74d4ad, magic: 0x9be7c7 },
    star:      { cover: 0x28254d, shadow: 0x17152e, rune: 0xe0b3ff, magic: 0xd9c0ff },
  };
  const m = map[element] || map.dark;
  out.style.bookCover = rgba(m.cover);
  out.style.bookCoverShadow = rgba(m.shadow);
  out.style.bookRune = rgba(m.rune);
  out.style.magic = rgba(m.magic);
  return out;
}

export function resolveHeroSpec(spec = DEFAULT_HERO_SPEC, options = {}) {
  let out = withHeroOptions(spec, options);
  out = applyPaletteVariant(out, out.appearance.paletteVariant);
  out = applyElementPalette(out, options.element || 'dark');
  return out;
}
