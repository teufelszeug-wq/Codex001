import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const html=fs.readFileSync(new URL('./開発進捗.html',import.meta.url),'utf8');
const data=JSON.parse(fs.readFileSync(new URL('./development-status.json',import.meta.url),'utf8'));
test('dashboard contains every development item and distinguishes incomplete work',()=>{
  assert.equal((html.match(/<article data-status=/g)??[]).length,data.items.length);
  for(const item of data.items)assert.ok(html.includes(item.name));
  assert.ok(html.includes('常時監視ではありません'));assert.ok(html.includes('C01-S07で停止中'));
});
test('all status filters hide other cards and restore all cards',()=>{
  const buttons=['all','verified','partial','pending'].map(filter=>({dataset:{filter},setAttribute(k,v){this[k]=v;},addEventListener(k,fn){this.click=fn;}}));
  const cards=data.items.map(x=>({dataset:{status:x.status},hidden:false}));
  vm.runInNewContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],{document:{querySelectorAll:s=>s==='[data-filter]'?buttons:cards}});
  for(const button of buttons){button.click();for(const card of cards)assert.equal(card.hidden,button.dataset.filter!=='all'&&card.dataset.status!==button.dataset.filter);assert.equal(button['aria-pressed'],'true');}
  buttons[0].click();assert.ok(cards.every(c=>!c.hidden));
});
