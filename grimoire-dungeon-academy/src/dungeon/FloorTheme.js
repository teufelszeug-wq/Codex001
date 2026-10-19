export const FLOOR_THEMES = {
  1: { name:'学園地下', floor:0x303442, wall:0x666b78, wallDark:0x272a35, accent:0xc7a85b },
  2: { name:'図書館迷宮', floor:0x4b3829, wall:0x2f241f, wallDark:0x17110f, accent:0x9b6a3d },
  3: { name:'魔法実験区画', floor:0x263044, wall:0x48556b, wallDark:0x19202c, accent:0x4fc3c8 },
  4: { name:'封印領域', floor:0x191321, wall:0x392746, wallDark:0x0f0b14, accent:0x8d55c7 }
};
export function getFloorTheme(floor) { return FLOOR_THEMES[floor] ?? FLOOR_THEMES[((floor - 1) % 4) + 1]; }
