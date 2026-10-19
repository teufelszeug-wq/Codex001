const WALK_BASE = Object.freeze({
  bobY:       [0, 1, 2, 1, 0, 1],
  legLeftX:   [-3, -2, 0, 2, 3, 1],
  legRightX:  [3, 2, 0, -2, -3, -1],
  footLeftY:  [0, 0, -1, -2, -1, 0],
  footRightY: [-1, -2, -1, 0, 0, -1],
  armLeftX:   [2, 1, 0, -1, -2, -1],
  armRightX:  [-2, -1, 0, 1, 2, 1],
  capeX:      [0, 1, 2, 1, 0, -1],
  hairTipX:   [0, 1, 2, 1, 0, -1],
  bookY:      [0, 1, 1, 0, -1, -1],
});

export const MOTION_LIBRARY = Object.freeze({
  idle:      { frames: 4, loop: true },
  walk:      { frames: 6, loop: true },
  castprep:  { frames: 3, loop: false },
  cast:      { frames: 6, loop: true },
  release:   { frames: 4, loop: false },
  dash:      { frames: 6, loop: true },
  jump:      { frames: 5, loop: false },
  landing:   { frames: 4, loop: false },
  damage:    { frames: 3, loop: false },
  fallen:    { frames: 2, loop: false },
  recovery:  { frames: 5, loop: false },
  pickup:    { frames: 5, loop: false },
  inspect:   { frames: 6, loop: true },
  opendoor:  { frames: 5, loop: false },
  sit:       { frames: 4, loop: true },
});

const IDLE_BOB = [0, 0, 1, 0];
const CAST_FLOAT = [0, -1, -2, -1, 0, -1];
const CAST_SWAY = [0, 1, 1, 0, -1, -1];

const WEIGHT_PROFILE = Object.freeze({
  light:  { strideNum: 4, strideDen: 3, bobNum: 1, bobDen: 1, armNum: 4, armDen: 3 },
  medium: { strideNum: 1, strideDen: 1, bobNum: 1, bobDen: 1, armNum: 1, armDen: 1 },
  heavy:  { strideNum: 2, strideDen: 3, bobNum: 2, bobDen: 3, armNum: 1, armDen: 2 },
});

function scaleInt(v, num, den) { return Math.round((v * num) / den); }
function frameIndex(frame, count) { return ((frame % count) + count) % count; }

function commonPose(motion, frame, direction) {
  return {
    motion, frame, direction,
    rootOffset: [0, 0],
    anchorOffsets: {},
    states: {
      book: 'closed-down', hair: 'rest', cape: 'rest', expression: 'neutral',
      body: 'upright', magic: 'none', prop: 'none', weaponPose: 'carry',
    },
  };
}

function buildWalkPose(frame, direction, equipment) {
  const f = frameIndex(frame, 6);
  const profile = WEIGHT_PROFILE[equipment?.weight] || WEIGHT_PROFILE.medium;
  const strideL = scaleInt(WALK_BASE.legLeftX[f], profile.strideNum, profile.strideDen);
  const strideR = scaleInt(WALK_BASE.legRightX[f], profile.strideNum, profile.strideDen);
  const armL = scaleInt(WALK_BASE.armLeftX[f], profile.armNum, profile.armDen);
  const armR = scaleInt(WALK_BASE.armRightX[f], profile.armNum, profile.armDen);
  const bob = scaleInt(WALK_BASE.bobY[f], profile.bobNum, profile.bobDen);
  const p = commonPose('walk', f, direction);
  p.rootOffset = [0, bob];
  p.anchorOffsets = {
    handL: [armL, 0], handR: [armR, 0],
    kneeL: [strideL, 0], kneeR: [strideR, 0],
    footL: [strideL, WALK_BASE.footLeftY[f]], footR: [strideR, WALK_BASE.footRightY[f]],
    cape: [WALK_BASE.capeX[f], 0], book: [armL - 1, WALK_BASE.bookY[f]],
    staff: [armL - 1, 0], hairTipL: [WALK_BASE.hairTipX[f], 0], hairTipR: [-WALK_BASE.hairTipX[f], 0],
  };
  p.states.hair = equipment?.weight === 'heavy' ? 'walk-low' : 'walk';
  p.states.cape = equipment?.weight === 'heavy' ? 'walk-low' : 'walk';
  p.states.weaponPose = equipment?.weaponType === 'staff' ? 'staff-walk' : 'carry';
  return p;
}

export function buildPose({ motion = 'walk', frame = 0, direction = 'down', equipment = {} } = {}) {
  if (motion === 'walk') return buildWalkPose(frame, direction, equipment);
  const count = MOTION_LIBRARY[motion]?.frames || 1;
  const f = frameIndex(frame, count);
  const p = commonPose(motion, f, direction);

  if (motion === 'idle') {
    p.rootOffset = [0, IDLE_BOB[f]];
    p.anchorOffsets = { handL: [0, -7], handR: [0, 0], book: [1, -5], cape: [0, 0] };
    p.states.book = 'closed-chest'; p.states.weaponPose = 'display';
  } else if (motion === 'castprep') {
    const step = [0, 1, 2][f];
    p.rootOffset = [0, -step];
    p.anchorOffsets = { handL: [-step, -7-step], handR: [step, -8-step], book: [2, -9-step], cape: [0, step ? -1 : 0] };
    p.states.book = f < 2 ? 'opening' : 'open-forward'; p.states.hair = 'lift'; p.states.cape = 'lift'; p.states.magic = f === 2 ? 'spark' : 'none';
  } else if (motion === 'cast') {
    p.rootOffset = [0, CAST_FLOAT[f]];
    p.anchorOffsets = { handL: [-2, -10], handR: [2, -10], book: [2, -12], cape: [CAST_SWAY[f], -1], hairTipL: [CAST_SWAY[f], -1], hairTipR: [-CAST_SWAY[f], -1] };
    p.states.book = 'open-forward'; p.states.hair = 'lift'; p.states.cape = 'lift'; p.states.magic = 'circle'; p.states.expression = 'focus';
  } else if (motion === 'release') {
    const dx = [0, 2, 4, 2][f];
    p.anchorOffsets = { handL: [-1, -10], handR: [dx, -10], book: [2, -12], cape: [-1, -1], hairTipL: [-1, 0], hairTipR: [1, 0] };
    p.states.book = 'open-forward'; p.states.magic = f < 3 ? 'burst' : 'spark'; p.states.expression = 'focus';
  } else if (motion === 'dash') {
    const phase = [0, 2, 4, 2, 0, -1][f];
    p.rootOffset = [phase, 1];
    p.anchorOffsets = { handL: [-2, 2], handR: [-4, 1], footL: [4, -1], footR: [-4, 0], kneeL: [3, 0], kneeR: [-3, 0], cape: [-4, 1], hairTipL: [-5, 1], hairTipR: [-5, 1], book: [-3, 2] };
    p.states.body = 'lean-forward'; p.states.hair = 'stream'; p.states.cape = 'stream';
  } else if (motion === 'jump') {
    const y = [0, -4, -8, -10, -7][f];
    p.rootOffset = [0, y];
    p.anchorOffsets = { kneeL: [-2, -2], kneeR: [2, -2], footL: [-2, -5], footR: [2, -5], handL: [-1, -2], handR: [1, -2], cape: [0, 2], hairTipL: [0, 2], hairTipR: [0, 2], book: [-1, -1] };
    p.states.body = 'air'; p.states.cape = 'float'; p.states.hair = 'float';
  } else if (motion === 'landing') {
    const crouch = [7, 5, 3, 0][f];
    p.rootOffset = [0, crouch];
    p.anchorOffsets = { kneeL: [-2, -4], kneeR: [2, -4], footL: [-2, 0], footR: [2, 0], handL: [-2, 2], handR: [2, 2], cape: [0, 2] };
    p.states.body = f < 3 ? 'crouch' : 'upright'; p.states.cape = 'settle';
  } else if (motion === 'damage') {
    p.rootOffset = [[0,0],[3,-1],[-1,1]][f];
    p.anchorOffsets = { handL: [-2, 1], handR: [3, -1], book: [-1, 2], cape: [-2, 0], hairTipL: [-2, 0], hairTipR: [-1, 0] };
    p.states.body = 'recoil'; p.states.expression = 'hurt';
  } else if (motion === 'fallen') {
    p.rootOffset = [0, 10]; p.states.body = 'fallen'; p.states.book = 'fallen'; p.states.expression = 'closed';
  } else if (motion === 'recovery') {
    const y = [10, 8, 5, 2, 0][f];
    p.rootOffset = [0, y]; p.anchorOffsets = { handL: [-2, 2], handR: [2, 1], book: [-1, 2] };
    p.states.body = f < 2 ? 'kneel' : f < 4 ? 'rise' : 'upright'; p.states.expression = f < 2 ? 'closed' : 'neutral';
  } else if (motion === 'pickup') {
    const bend = [0, 3, 6, 4, 0][f];
    p.rootOffset = [0, bend]; p.anchorOffsets = { handR: [0, 6], handL: [1, 2], book: [2, 2] };
    p.states.body = f === 2 ? 'deep-bend' : f ? 'bend' : 'upright'; p.states.prop = f >= 2 ? 'item' : 'none';
  } else if (motion === 'inspect') {
    const sway = [0, 1, 1, 0, -1, -1][f];
    p.anchorOffsets = { handL: [0, -9], handR: [sway, -7], book: [2, -7], cape: [0,0] };
    p.states.book = 'closed-chest'; p.states.expression = f === 2 || f === 3 ? 'curious' : 'neutral'; p.states.prop = 'inspect';
  } else if (motion === 'opendoor') {
    const reach = [0, 2, 5, 7, 4][f];
    p.anchorOffsets = { handR: [reach, -2], handL: [0, -2], book: [-1, 0] };
    p.states.body = f > 1 ? 'lean-forward' : 'upright'; p.states.prop = 'door';
  } else if (motion === 'sit') {
    p.rootOffset = [0, 12 + IDLE_BOB[f]];
    p.anchorOffsets = { kneeL: [-3, -4], kneeR: [3, -4], footL: [-5, -2], footR: [5, -2], handL: [2, 1], handR: [-2, 1], book: [3, 1] };
    p.states.body = 'sit'; p.states.book = 'closed-lap';
  }

  if (equipment?.weaponType === 'staff' && ['idle','walk','inspect'].includes(motion)) p.states.weaponPose = 'staff-carry';
  return p;
}

export function layerOrder(direction) {
  switch (direction) {
    case 'up': return ['magicBack','weaponBack','cape','hairBack','legs','torso','arms','head','hairFront','magicFront','prop'];
    case 'left': return ['magicBack','cape','hairBack','legBack','armRight','torso','weaponBack','head','hairFront','legFront','armLeft','weaponFront','magicFront','prop'];
    case 'right': return ['magicBack','cape','hairBack','legBack','armLeft','torso','weaponBack','head','hairFront','legFront','armRight','weaponFront','magicFront','prop'];
    default: return ['magicBack','cape','hairBack','legs','torso','arms','weaponBack','weaponFront','head','hairFront','magicFront','prop'];
  }
}
