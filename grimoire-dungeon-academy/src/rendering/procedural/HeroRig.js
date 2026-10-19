export const HERO_RIG = Object.freeze({
  root: [48, 57],
  anchors: {
    head: [48, 28],
    neck: [48, 44],
    shoulderL: [38, 49],
    shoulderR: [58, 49],
    elbowL: [33, 61],
    elbowR: [63, 61],
    handL: [31, 70],
    handR: [65, 70],
    hipL: [43, 68],
    hipR: [53, 68],
    kneeL: [42, 79],
    kneeR: [54, 79],
    footL: [40, 90],
    footR: [56, 90],
    book: [29, 66],
    staff: [27, 65],
    cape: [48, 49],
    prop: [48, 71],
  },
});

export function offsetAnchor(name, pose = {}) {
  const base = HERO_RIG.anchors[name];
  if (!base) throw new Error(`Unknown anchor: ${name}`);
  const [dx, dy] = pose.anchorOffsets?.[name] || [0, 0];
  const [rx, ry] = pose.rootOffset || [0, 0];
  return [base[0] + dx + rx, base[1] + dy + ry];
}
