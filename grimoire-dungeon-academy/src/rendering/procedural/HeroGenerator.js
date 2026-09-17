import { PixelSurface } from './PixelSurface.js';
import { DEFAULT_HERO_SPEC, resolveHeroSpec } from './HeroSpec.js';
import { offsetAnchor } from './HeroRig.js';
import { buildPose, layerOrder, MOTION_LIBRARY } from './HeroMotion.js';
import { correctionPatch } from './HeroCorrections.js';

function drawOutlinedEllipse(s, cx, cy, rx, ry, fill, outline, thickness = 1) {
  s.ellipse(cx, cy, rx + thickness, ry + thickness, outline);
  s.ellipse(cx, cy, rx, ry, fill);
}

function drawOutlinedPolygon(s, points, fill, outline) {
  const center = points.reduce((acc, [x,y]) => [acc[0]+x, acc[1]+y], [0,0]).map(v => v / points.length);
  const expanded = points.map(([x,y]) => {
    const dx = x-center[0], dy = y-center[1];
    const len = Math.max(1, Math.hypot(dx,dy));
    return [Math.round(x + dx/len), Math.round(y + dy/len)];
  });
  s.polygon(expanded, outline);
  s.polygon(points, fill);
}

function drawSegment(s, a, b, width, fill, outline) {
  const [x0, y0] = a, [x1, y1] = b;
  const minX = Math.floor(Math.min(x0, x1) - width - 1);
  const maxX = Math.ceil(Math.max(x0, x1) + width + 1);
  const minY = Math.floor(Math.min(y0, y1) - width - 1);
  const maxY = Math.ceil(Math.max(y0, y1) + width + 1);
  const paint = (r, color) => {
    for (let y = minY; y <= maxY; y++) for (let x = minX; x <= maxX; x++) {
      const vx = x1 - x0, vy = y1 - y0, wx = x - x0, wy = y - y0;
      const c1 = vx * wx + vy * wy, c2 = vx * vx + vy * vy;
      const t = c2 === 0 ? 0 : Math.max(0, Math.min(1, c1 / c2));
      const px = x0 + t * vx, py = y0 + t * vy;
      if ((x - px) ** 2 + (y - py) ** 2 <= r ** 2) s.set(x, y, color);
    }
  };
  paint(width + 1, outline); paint(width, fill);
}

function drawDiamond(s, cx, cy, r, color) {
  s.polygon([[cx,cy-r],[cx+r,cy],[cx,cy+r],[cx-r,cy]], color);
}

export class HeroGenerator {
  constructor(spec = DEFAULT_HERO_SPEC) { this.spec = spec; }

  generate(options = {}) {
    const {
      direction = 'down', motion = 'walk', frame = 0, element = 'dark',
      hairStyle, outfit, paletteVariant, weaponType, weight, grimoireId,
    } = options;
    const spec = resolveHeroSpec(this.spec, { element, hairStyle, outfit, paletteVariant, weaponType, weight, grimoireId });
    const pose = buildPose({ direction, motion, frame, equipment: spec.equipment });
    const layers = this.#buildLayers(spec, pose);
    const out = new PixelSurface(spec.canvas.width, spec.canvas.height);
    for (const name of layerOrder(direction)) if (layers[name]) out.blit(layers[name]);
    out.applyPatch(correctionPatch(direction, motion, frame));
    return out;
  }

  generateWalkSet(element = 'dark', options = {}) {
    const result = {};
    for (const direction of ['down','left','right','up']) {
      result[direction] = [];
      for (let frame = 0; frame < 6; frame++) result[direction].push(this.generate({ ...options, direction, motion:'walk', frame, element }));
    }
    return result;
  }

  generateMotionSet(motion, { direction = 'down', element = 'dark', ...options } = {}) {
    const frames = MOTION_LIBRARY[motion]?.frames || 1;
    return Array.from({ length: frames }, (_, frame) => this.generate({ ...options, direction, motion, frame, element }));
  }

  #buildLayers(spec, pose) {
    const make = () => new PixelSurface(spec.canvas.width, spec.canvas.height);
    const layers = {};
    for (const name of ['magicBack','cape','hairBack','legs','legBack','legFront','torso','arms','armLeft','armRight','weaponBack','weaponFront','head','hairFront','magicFront','prop']) layers[name] = make();

    if (pose.states.body === 'fallen') {
      this.#drawFallen(layers, spec, pose);
      this.#drawMagic(layers, spec, pose);
      return layers;
    }

    this.#drawCape(layers.cape, spec, pose);
    this.#drawHairBack(layers.hairBack, spec, pose);
    this.#drawLegs(layers, spec, pose);
    this.#drawTorso(layers.torso, spec, pose);
    this.#drawArms(layers, spec, pose);
    this.#drawWeapon(layers, spec, pose);
    this.#drawHead(layers.head, spec, pose);
    this.#drawHairFront(layers.hairFront, spec, pose);
    this.#drawMagic(layers, spec, pose);
    this.#drawProp(layers.prop, spec, pose);

    if (pose.direction === 'up') this.#convertToBackView(layers, spec, pose);
    return layers;
  }

  #convertToBackView(layers, spec, pose) {
    const S = spec.style, [, rootY] = pose.rootOffset || [0,0];
    layers.head.clear(); layers.hairFront.clear();
    drawOutlinedEllipse(layers.head, 48, 28 + rootY, 16, 15, S.hair, S.outline);
    layers.head.ellipse(48, 24 + rootY, 12, 9, S.hairMid);
    layers.head.line(39, 23+rootY, 57, 23+rootY, S.hairHighlight);
  }

  #drawHead(s, spec, pose) {
    const S = spec.style, [, rootY] = pose.rootOffset || [0,0];
    const bodyShift = pose.states.body === 'recoil' ? -1 : 0;
    const cy = 29 + rootY + bodyShift;
    drawOutlinedEllipse(s, 48, cy, 16, 15, S.skin, S.outline);
    s.ellipse(48, cy + 9, 13, 5, S.skinShadow); s.ellipse(48, cy + 7, 13, 5, S.skin);

    if (pose.direction === 'left') {
      s.rect(40,cy,7,2,S.outline); s.rect(41,cy+1,5,3,S.eye); s.set(42,cy+1,S.eyeHighlight);
      s.rect(47,cy+8,2,1,S.skinShadow);
    } else if (pose.direction === 'right') {
      s.rect(49,cy,7,2,S.outline); s.rect(50,cy+1,5,3,S.eye); s.set(53,cy+1,S.eyeHighlight);
      s.rect(47,cy+8,2,1,S.skinShadow);
    } else {
      const closed = pose.states.expression === 'closed';
      const hurt = pose.states.expression === 'hurt';
      const curious = pose.states.expression === 'curious';
      const focus = pose.states.expression === 'focus';
      if (closed) {
        s.line(38,cy+2,45,cy+2,S.eyeShadow); s.line(51,cy+2,58,cy+2,S.eyeShadow);
      } else if (hurt) {
        s.line(38,cy,45,cy+2,S.eyeShadow); s.line(51,cy+2,58,cy,S.eyeShadow);
      } else {
        const eyeY = focus ? cy : cy+1;
        s.rect(37,eyeY-1,9,2,S.outline); s.rect(50,eyeY-1,9,2,S.outline);
        s.rect(39,eyeY+1,6,4,S.eye); s.rect(51,eyeY+1,6,4,S.eye);
        s.rect(40,eyeY+1,4,2,S.eyeShadow); s.rect(52,eyeY+1,4,2,S.eyeShadow);
        s.set(40,eyeY+1,S.eyeHighlight); s.set(55,eyeY+1,S.eyeHighlight);
        if (curious) s.set(57,eyeY,S.eyeHighlight);
      }
      s.set(37,cy+7,S.blush); s.set(59,cy+7,S.blush);
      s.rect(47,cy+9,3,1,S.skinShadow);
    }
  }

  #drawHairBack(s, spec, pose) {
    const S = spec.style, style = spec.appearance.hairStyle;
    const [, rootY] = pose.rootOffset || [0,0];
    const swayL = pose.anchorOffsets?.hairTipL?.[0] || 0, swayR = pose.anchorOffsets?.hairTipR?.[0] || 0;
    s.ellipse(48, 25 + rootY, 20, 18, S.outline); s.ellipse(48, 25 + rootY, 19, 17, S.hair);
    s.ellipse(48, 21 + rootY, 15, 11, S.hairMid);

    if (style === 'bob') {
      drawOutlinedPolygon(s, [[30,29+rootY],[34,46+rootY],[42,51+rootY],[48,46+rootY],[54,51+rootY],[62,46+rootY],[66,29+rootY]], S.hair, S.outline);
      s.line(34,35+rootY,39,48+rootY,S.hairHighlight); s.line(62,35+rootY,57,48+rootY,S.hairHighlight);
    } else if (style === 'ponytail') {
      drawOutlinedPolygon(s, [[31,29+rootY],[34,52+rootY],[40,58+rootY],[45,46+rootY],[51,46+rootY],[56,58+rootY],[62,52+rootY],[65,29+rootY]], S.hair, S.outline);
      drawOutlinedPolygon(s, [[60,22+rootY],[72+swayR,32+rootY],[69+swayR,59+rootY],[61,50+rootY]], S.hair, S.outline);
      s.line(64,31+rootY,68+swayR,54+rootY,S.hairHighlight);
    } else {
      drawOutlinedPolygon(s, [[29,29+rootY],[31,54+rootY],[34+swayL,76+rootY],[40+swayL,82+rootY],[45,70+rootY],[45,38+rootY]], S.hair, S.outline);
      drawOutlinedPolygon(s, [[51,38+rootY],[51,70+rootY],[56+swayR,82+rootY],[62+swayR,76+rootY],[65,54+rootY],[67,29+rootY]], S.hair, S.outline);
      s.polygon([[34,41+rootY],[37,43+rootY],[38+swayL,73+rootY],[41+swayL,75+rootY],[42,43+rootY]],S.hairMid);
      s.polygon([[54,43+rootY],[55+swayR,75+rootY],[58+swayR,73+rootY],[59,43+rootY],[62,41+rootY]],S.hairMid);
      s.line(34,43+rootY,38+swayL,75+rootY,S.hairHighlight); s.line(62,43+rootY,58+swayR,75+rootY,S.hairHighlight);
    }
  }

  #drawHairFront(s, spec, pose) {
    const S = spec.style, [, rootY] = pose.rootOffset || [0,0];
    const y = 14 + rootY;
    const bangs = [[31,y+7],[34,y+2],[39,y],[45,y+1],[48,y+5],[51,y+1],[58,y],[63,y+3],[66,y+8],[61,y+13],[57,y+10],[55,y+15],[51,y+11],[48,y+16],[44,y+11],[41,y+15],[39,y+10],[34,y+13]];
    drawOutlinedPolygon(s, bangs, S.hair, S.outline);
    s.line(36,y+4,43,y+2,S.hairHighlight); s.line(53,y+2,60,y+4,S.hairHighlight);
    s.rect(45,y+2,6,2,S.hairMid);
  }

  #drawCape(s, spec, pose) {
    const S = spec.style, [cx, cy] = offsetAnchor('cape', pose), dx = pose.anchorOffsets?.cape?.[0] || 0;
    const long = spec.appearance.outfit === 'archmage' ? 25 : 20;
    drawOutlinedPolygon(s, [[cx-15,cy-1],[cx+15,cy-1],[cx+13+dx,cy+long],[cx+5,cy+long-4],[cx,cy+long+2],[cx-5,cy+long-4],[cx-13+dx,cy+long]], S.cape, S.outline);
    s.line(cx-12,cy+2,cx+12,cy+2,S.gold);
    s.set(cx-12,cy+3,S.goldLight); s.set(cx+12,cy+3,S.goldLight);
  }

  #drawTorso(s, spec, pose) {
    const S = spec.style, [, rootY] = pose.rootOffset || [0,0];
    let y = 45 + rootY;
    if (pose.states.body === 'crouch' || pose.states.body === 'deep-bend') y += 2;
    const outfit = spec.appearance.outfit;
    if (outfit === 'robe') {
      drawOutlinedPolygon(s, [[35,y],[61,y],[66,y+31],[30,y+31],[34,y+16]], S.uniform, S.outline);
      s.polygon([[39,y+2],[57,y+2],[59,y+22],[37,y+22]],S.uniformLight);
    } else if (outfit === 'archmage') {
      drawOutlinedPolygon(s, [[34,y],[62,y],[67,y+31],[29,y+31],[33,y+13]], S.uniformShadow, S.outline);
      drawOutlinedPolygon(s, [[37,y+1],[59,y+1],[62,y+27],[34,y+27]], S.uniform, S.outline);
      s.line(35,y+25,61,y+25,S.goldLight);
    } else {
      drawOutlinedPolygon(s, [[35,y],[61,y],[63,y+26],[58,y+29],[52,y+27],[48,y+31],[44,y+27],[38,y+29],[33,y+26]], S.uniform, S.outline);
      s.polygon([[39,y+2],[57,y+2],[58,y+21],[38,y+21]],S.uniformLight);
    }
    s.rect(40,y+1,16,5,S.shirt); s.line(48,y+5,48,y+22,S.gold);
    s.polygon([[40,y+5],[47,y+10],[44,y+16],[38,y+10]],S.ribbon);
    s.polygon([[56,y+5],[49,y+10],[52,y+16],[58,y+10]],S.ribbon);
    drawDiamond(s,48,y+9,2,S.goldLight);
    s.line(35,y+23,61,y+23,S.gold); s.set(35,y+24,S.goldLight); s.set(61,y+24,S.goldLight);
  }

  #drawLegs(layers, spec, pose) {
    const S = spec.style;
    let hipL = offsetAnchor('hipL', pose), hipR = offsetAnchor('hipR', pose), kneeL = offsetAnchor('kneeL', pose), kneeR = offsetAnchor('kneeR', pose), footL = offsetAnchor('footL', pose), footR = offsetAnchor('footR', pose);
    if (pose.states.body === 'sit') { kneeL=[39,82]; kneeR=[57,82]; footL=[35,88]; footR=[61,88]; }
    const targetL = pose.direction === 'left' ? layers.legFront : pose.direction === 'right' ? layers.legBack : layers.legs;
    const targetR = pose.direction === 'left' ? layers.legBack : pose.direction === 'right' ? layers.legFront : layers.legs;
    drawSegment(targetL, hipL, kneeL, 4, S.uniformShadow, S.outline); drawSegment(targetL, kneeL, footL, 4, S.boot, S.outline);
    drawSegment(targetR, hipR, kneeR, 4, S.uniformShadow, S.outline); drawSegment(targetR, kneeR, footR, 4, S.boot, S.outline);
    for (const [target, foot] of [[targetL,footL],[targetR,footR]]) {
      target.rect(foot[0]-5,foot[1]-2,10,5,S.outline); target.rect(foot[0]-4,foot[1]-2,8,3,S.bootLight); target.rect(foot[0]-3,foot[1],7,2,S.boot);
      target.rect(foot[0]-3,foot[1]-5,6,2,S.gold);
    }
  }

  #drawArms(layers, spec, pose) {
    const S = spec.style;
    let shoulderL = offsetAnchor('shoulderL', pose), shoulderR = offsetAnchor('shoulderR', pose), elbowL = offsetAnchor('elbowL', pose), elbowR = offsetAnchor('elbowR', pose), handL = offsetAnchor('handL', pose), handR = offsetAnchor('handR', pose);
    if (pose.states.body === 'lean-forward') { shoulderL[0]+=2; shoulderR[0]+=2; elbowL[0]+=3; elbowR[0]+=3; }
    if (pose.states.body === 'bend' || pose.states.body === 'deep-bend') { shoulderL[1]+=2; shoulderR[1]+=2; }
    const leftLayer = pose.direction === 'left' ? layers.armLeft : pose.direction === 'right' ? layers.armLeft : layers.arms;
    const rightLayer = pose.direction === 'left' ? layers.armRight : pose.direction === 'right' ? layers.armRight : layers.arms;
    drawSegment(leftLayer, shoulderL, elbowL, 4, S.uniform, S.outline); drawSegment(leftLayer, elbowL, handL, 4, S.uniform, S.outline);
    drawSegment(rightLayer, shoulderR, elbowR, 4, S.uniform, S.outline); drawSegment(rightLayer, elbowR, handR, 4, S.uniform, S.outline);
    leftLayer.line(shoulderL[0],shoulderL[1]+3,elbowL[0],elbowL[1],S.gold); rightLayer.line(shoulderR[0],shoulderR[1]+3,elbowR[0],elbowR[1],S.gold);
    drawOutlinedEllipse(leftLayer,handL[0],handL[1],2,2,S.skin,S.outline); drawOutlinedEllipse(rightLayer,handR[0],handR[1],2,2,S.skin,S.outline);
  }

  #drawWeapon(layers, spec, pose) {
    if (spec.equipment.weaponType === 'staff') return this.#drawStaff(layers, spec, pose);
    return this.#drawBook(layers, spec, pose);
  }

  #drawBook(layers, spec, pose) {
    const S = spec.style, state = pose.states.book || 'closed-down', [bx,by] = offsetAnchor('book',pose);
    const target = pose.direction === 'up' ? layers.weaponBack : layers.weaponFront;
    if (state === 'fallen') return;
    if (state === 'opening' || state === 'open-forward') {
      const spread = state === 'opening' ? 10 : 14;
      drawOutlinedPolygon(target,[[bx-spread,by-4],[bx-1,by-1],[bx-1,by+11],[bx-spread,by+8]],S.bookCover,S.outline);
      drawOutlinedPolygon(target,[[bx+1,by-1],[bx+spread,by-4],[bx+spread,by+8],[bx+1,by+11]],S.bookCover,S.outline);
      target.polygon([[bx-spread+2,by-2],[bx-2,by],[bx-2,by+8],[bx-spread+2,by+6]],S.page);
      target.polygon([[bx+2,by],[bx+spread-2,by-2],[bx+spread-2,by+6],[bx+2,by+8]],S.page);
      target.line(bx,by-1,bx,by+10,S.bookEdge); target.set(bx-7,by+2,S.bookRune); target.set(bx+7,by+2,S.bookRune);
      return;
    }
    const w=spec.grimoire.width,h=spec.grimoire.height;
    let x=bx-5,y=by-5;
    if (state === 'closed-chest') { x=bx-9; y=by-9; }
    if (state === 'closed-lap') { x=bx-8; y=by; }
    target.rect(x-1,y-1,w+2,h+2,S.outline); target.rect(x,y,w,h,S.bookCover); target.rect(x,y,w,3,S.bookCoverShadow);
    target.rect(x+2,y+2,w-4,2,S.bookEdge); target.line(x+2,y+4,x+2,y+h-3,S.bookEdge);
    drawDiamond(target,x+Math.floor(w/2),y+10,3,S.bookRune); target.set(x+Math.floor(w/2),y+5,S.goldLight);
  }

  #drawStaff(layers, spec, pose) {
    const S=spec.style,[sx,sy]=offsetAnchor('staff',pose),target=pose.direction==='up'?layers.weaponBack:layers.weaponFront;
    target.line(sx,sy-14,sx+2,sy+20,S.outline); target.line(sx+1,sy-14,sx+3,sy+20,S.bootLight);
    drawOutlinedEllipse(target,sx,sy-17,4,4,S.magic,S.outline); drawDiamond(target,sx,sy-17,2,S.goldLight);
  }

  #drawMagic(layers,spec,pose){
    const state=pose.states.magic;if(!state||state==='none')return;const S=spec.style,front=layers.magicFront,back=layers.magicBack;
    if(state==='spark'){
      for(const [x,y] of [[29,57],[68,53],[48,43],[34,39]]){drawDiamond(front,x,y,1,S.magic);front.set(x+2,y,S.goldLight);}
    }else if(state==='circle'){
      const r=22; for(let i=0;i<32;i++){const a=(Math.PI*2*i)/32;const x=Math.round(48+Math.cos(a)*r),y=Math.round(58+Math.sin(a)*9);front.set(x,y,S.magic);if(i%4===0)drawDiamond(front,x,y,1,S.goldLight);} back.line(34,58,62,58,S.magic);
    }else if(state==='burst'){
      for(const [dx,dy] of [[0,-14],[0,14],[-16,0],[16,0],[-11,-9],[11,-9],[-11,9],[11,9]]) front.line(48,55,48+dx,55+dy,S.magic);
      drawDiamond(front,48,55,4,S.goldLight);
    }
  }

  #drawProp(s,spec,pose){const S=spec.style;if(pose.states.prop==='item'){drawDiamond(s,48,83,3,S.magic);s.set(48,78,S.goldLight);}else if(pose.states.prop==='inspect'){s.rect(61,58,4,6,S.outline);s.rect(62,59,2,4,S.goldLight);}else if(pose.states.prop==='door'){s.rect(73,46,2,18,S.gold);s.set(72,56,S.goldLight);}}

  #drawFallen(layers,spec,pose){
    const S=spec.style,s=layers.torso;
    drawOutlinedEllipse(s,45,72,16,12,S.hair,S.outline); drawOutlinedEllipse(s,48,73,13,10,S.skin,S.outline);
    drawOutlinedPolygon(s,[[47,72],[67,68],[76,74],[66,82],[45,82]],S.uniform,S.outline); s.line(56,72,69,76,S.gold);
    drawSegment(s,[63,78],[79,81],4,S.uniformShadow,S.outline); drawSegment(s,[70,81],[86,83],4,S.boot,S.outline);
    layers.hairFront.polygon([[31,67],[38,61],[54,62],[59,69],[52,74],[41,72]],S.hair); layers.hairFront.line(36,64,51,65,S.hairHighlight);
    layers.weaponFront.rect(25,78,14,9,S.outline); layers.weaponFront.rect(26,79,12,7,S.bookCover); drawDiamond(layers.weaponFront,32,82,2,S.bookRune);
  }
}
