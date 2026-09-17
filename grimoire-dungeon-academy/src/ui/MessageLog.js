export class MessageLog {
  constructor(scene,x,y,width=450) { this.lines=[]; this.text=scene.add.text(x,y,'',{fontFamily:'monospace',fontSize:'13px',color:'#eee7d5',wordWrap:{width}}).setScrollFactor(0).setDepth(100); }
  push(message) { this.lines.push(message); this.lines=this.lines.slice(-4); this.text.setText(this.lines.join('\n')); }
}
