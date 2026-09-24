import { GameState } from './GameState.js';
const KEY='gda-save-v1';
function validate(data){
 if(!data||typeof data!=='object'||Array.isArray(data)||typeof data.name!=='string'||data.name.length>24)throw Error('Invalid save');
 for(const k of ['level','floor','maxHP','maxMP','hp','mp','seed'])if(!Number.isFinite(data[k])||data[k]<0)throw Error('Invalid stats');
 if(!Number.isInteger(data.floor)||data.floor<1||data.floor>10000||data.hp>data.maxHP||data.mp>data.maxMP||!Array.isArray(data.grimoires)||!data.grimoires.length||data.grimoires.some(x=>!['dark','fire','light'].includes(x))||!data.grimoires.includes(data.equippedGrimoire))throw Error('Invalid equipment');
 if(data.snapshot){const d=data.snapshot;
 const pos=p=>p&&Number.isInteger(p.x)&&Number.isInteger(p.y)&&p.x>=0&&p.y>=0&&p.x<40&&p.y<32&&d.tiles[p.y][p.x]===0;
 if(!Array.isArray(d.tiles)||d.tiles.length!==32||d.tiles.some(row=>!Array.isArray(row)||row.length!==40||row.some(v=>v!==0&&v!==1)))throw Error('Invalid map');
 if(!pos({x:data.playerX,y:data.playerY})||!pos(d.stairs)||!Array.isArray(d.enemies)||d.enemies.length>100||d.enemies.some(e=>!pos(e)||!['slime','skeleton'].includes(e.type)||!Number.isFinite(e.hp)||e.hp<0)||!Array.isArray(d.explored)||d.explored.some(k=>typeof k!=='string'||!/^\d+,\d+$/.test(k)))throw Error('Invalid snapshot');
 }
 return new GameState(data);
}
export const SaveManager={
 lastError:null,
 exists(){return this.load()!==null;},
 save(state){try{localStorage.setItem(KEY,JSON.stringify(state.serialize()));this.lastError=null;return true;}catch(e){this.lastError=e.message;return false;}},
 load(){try{const raw=localStorage.getItem(KEY);if(!raw)return null;if(raw.length>500000)throw Error('Oversized save');return validate(JSON.parse(raw));}catch(e){this.lastError=e.message;return null;}},
 clear(){try{localStorage.removeItem(KEY);return true;}catch(e){this.lastError=e.message;return false;}}
};
