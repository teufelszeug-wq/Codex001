export class PixelSurface {
  constructor(width = 96, height = 96, transparent = 0x00000000) {
    this.width = width;
    this.height = height;
    this.pixels = new Uint32Array(width * height);
    this.clear(transparent);
  }

  clear(color = 0x00000000) {
    this.pixels.fill(color >>> 0);
    return this;
  }

  clone() {
    const copy = new PixelSurface(this.width, this.height);
    copy.pixels.set(this.pixels);
    return copy;
  }

  inBounds(x, y) {
    return x >= 0 && y >= 0 && x < this.width && y < this.height;
  }

  set(x, y, color) {
    x = Math.round(x); y = Math.round(y);
    if (!this.inBounds(x, y)) return;
    this.pixels[y * this.width + x] = color >>> 0;
  }

  get(x, y) {
    x = Math.round(x); y = Math.round(y);
    if (!this.inBounds(x, y)) return 0;
    return this.pixels[y * this.width + x] >>> 0;
  }

  rect(x, y, w, h, color) {
    x = Math.round(x); y = Math.round(y); w = Math.round(w); h = Math.round(h);
    for (let yy = y; yy < y + h; yy++) {
      for (let xx = x; xx < x + w; xx++) this.set(xx, yy, color);
    }
    return this;
  }

  line(x0, y0, x1, y1, color) {
    x0 = Math.round(x0); y0 = Math.round(y0); x1 = Math.round(x1); y1 = Math.round(y1);
    const dx = Math.abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
    const dy = -Math.abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
    let err = dx + dy;
    while (true) {
      this.set(x0, y0, color);
      if (x0 === x1 && y0 === y1) break;
      const e2 = 2 * err;
      if (e2 >= dy) { err += dy; x0 += sx; }
      if (e2 <= dx) { err += dx; y0 += sy; }
    }
    return this;
  }

  ellipse(cx, cy, rx, ry, color) {
    cx = Math.round(cx); cy = Math.round(cy);
    rx = Math.max(1, Math.round(rx)); ry = Math.max(1, Math.round(ry));
    for (let y = cy - ry; y <= cy + ry; y++) {
      const ny = (y - cy) / ry;
      const span = Math.floor(rx * Math.sqrt(Math.max(0, 1 - ny * ny)));
      for (let x = cx - span; x <= cx + span; x++) this.set(x, y, color);
    }
    return this;
  }

  polygon(points, color) {
    if (!points || points.length < 3) return this;
    const ys = points.map(([, y]) => Math.round(y));
    const minY = Math.max(0, Math.min(...ys));
    const maxY = Math.min(this.height - 1, Math.max(...ys));
    for (let y = minY; y <= maxY; y++) {
      const xs = [];
      for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
        const [xi, yi] = points[i];
        const [xj, yj] = points[j];
        const intersects = ((yi > y) !== (yj > y));
        if (!intersects) continue;
        const x = xi + ((y - yi) * (xj - xi)) / (yj - yi);
        xs.push(Math.round(x));
      }
      xs.sort((a, b) => a - b);
      for (let i = 0; i + 1 < xs.length; i += 2) {
        for (let x = xs[i]; x <= xs[i + 1]; x++) this.set(x, y, color);
      }
    }
    return this;
  }

  blit(source, ox = 0, oy = 0) {
    for (let y = 0; y < source.height; y++) {
      for (let x = 0; x < source.width; x++) {
        const color = source.get(x, y);
        if ((color >>> 24) === 0) continue;
        this.set(x + ox, y + oy, color);
      }
    }
    return this;
  }

  applyPatch(patch = []) {
    for (const p of patch) {
      if (p.clear) this.set(p.x, p.y, 0x00000000);
      else this.set(p.x, p.y, p.color >>> 0);
    }
    return this;
  }

  hash() {
    let h = 2166136261 >>> 0;
    for (const value of this.pixels) {
      h ^= value;
      h = Math.imul(h, 16777619) >>> 0;
    }
    return h.toString(16).padStart(8, '0');
  }
}
