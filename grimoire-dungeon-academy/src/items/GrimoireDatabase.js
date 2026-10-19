export const GRIMOIRES = {
  dark: { id:'dark', name:'夜陰のグリモア', element:'dark', color:0x9b59d0, edge:0xd2b36c, spell:'Shadow Bolt', mpCost:3, power:7, description:'影を凝縮して撃ち出す。' },
  fire: { id:'fire', name:'紅蓮のグリモア', element:'fire', color:0xe85b3f, edge:0xffc46b, spell:'Ember Lance', mpCost:4, power:9, description:'直線的な火炎魔法。' },
  light:{ id:'light', name:'白耀のグリモア', element:'light', color:0xf4e89b, edge:0xffffff, spell:'Lumen Dart', mpCost:3, power:7, description:'浄化の光弾。' }
};
export function getGrimoire(id) { return GRIMOIRES[id] ?? GRIMOIRES.dark; }
