import * as ROT from 'rot-js';
import { hashSeed } from '../core/RNG.js';

export class DungeonGenerator {
  constructor(width = 40, height = 32) { this.width = width; this.height = height; }
  generate(seed, floor) {
    ROT.RNG.setSeed(hashSeed(seed, floor));
    const tiles = Array.from({ length: this.height }, () => Array(this.width).fill(1));
    const digger = new ROT.Map.Digger(this.width, this.height, { roomWidth:[5,10], roomHeight:[4,8], corridorLength:[2,8], dugPercentage:0.28 });
    digger.create((x,y,value) => { tiles[y][x] = value; });
    const rooms = digger.getRooms();
    if (rooms.length < 2) throw new Error('Dungeon generation produced too few rooms');
    const center = room => ({ x: Math.floor((room.getLeft()+room.getRight())/2), y: Math.floor((room.getTop()+room.getBottom())/2) });
    const start = center(rooms[0]);
    const stairs = center(rooms[rooms.length - 1]);
    const candidates=[];
    for(let y=1;y<this.height-1;y++)for(let x=1;x<this.width-1;x++)if(tiles[y][x]===0&&Math.abs(x-start.x)+Math.abs(y-start.y)>6&&(x!==stairs.x||y!==stairs.y))candidates.push({x,y});
    const shuffled=ROT.RNG.shuffle(candidates),enemies=[];
    for(let i=0;i<Math.min(4+floor,shuffled.length);i++)enemies.push({...shuffled[i],type:(i+floor)%2===0?'slime':'skeleton'});
    return { tiles, rooms, start, stairs, enemies };
  }
}
