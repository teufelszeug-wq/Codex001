export const ROBES = {
  academy:{ body:0x222b59, shadow:0x151a38, trim:0xc7a85b, cape:0x303a70 },
  azure:{ body:0x244f78, shadow:0x17344f, trim:0xa6d9e8, cape:0x2e6996 }
};
export function robePalette(id) { return ROBES[id] ?? ROBES.academy; }
