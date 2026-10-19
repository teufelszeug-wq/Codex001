export function hashSeed(seed, floor) {
  let x = (seed ^ (floor * 0x9e3779b9)) >>> 0;
  x ^= x << 13; x ^= x >>> 17; x ^= x << 5;
  return (x >>> 0) || 1;
}
