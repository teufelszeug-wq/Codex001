export class Player {
  constructor(state, x, y) { this.state = state; this.x=x; this.y=y; this.direction='down'; this.walkFrame=0; }
  canMoveTo(x,y,tiles) { return y>=0 && x>=0 && y<tiles.length && x<tiles[0].length && tiles[y][x] === 0; }
  move(dx,dy,tiles) {
    const nx=this.x+dx, ny=this.y+dy;
    if (!this.canMoveTo(nx,ny,tiles)) return false;
    this.x=nx; this.y=ny;
    this.direction = dx<0?'left':dx>0?'right':dy<0?'up':'down';
    this.walkFrame=(this.walkFrame+1)%6;
    return true;
  }
}
