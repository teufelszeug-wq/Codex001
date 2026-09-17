const ROT = globalThis.ROT;
export class FOVSystem {
  constructor(tiles) { this.tiles = tiles; this.height = tiles.length; this.width = tiles[0].length; this.explored = new Set(); }
  isTransparent = (x,y) => x>=0 && y>=0 && x<this.width && y<this.height && this.tiles[y][x] === 0;
  compute(x,y,radius=8) {
    const visible = new Set();
    const fov = new ROT.FOV.PreciseShadowcasting(this.isTransparent, { topology: 4 });
    fov.compute(x,y,radius,(vx,vy) => { const key=`${vx},${vy}`; visible.add(key); this.explored.add(key); });
    return visible;
  }
}
