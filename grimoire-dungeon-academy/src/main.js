import Phaser from 'phaser';
import '@fontsource/noto-sans-jp/400.css';
import './styles.css';
import fontCharacters from './font-characters.js';
globalThis.Phaser=Phaser;
async function boot(){
 await document.fonts.load('14px "Noto Sans JP"',fontCharacters);
 const [{BootScene},{TitleScene},{CharacterCreateScene},{GameScene}]=await Promise.all([
  import('./scenes/BootScene.js'),import('./scenes/TitleScene.js'),import('./scenes/CharacterCreateScene.js'),import('./scenes/GameScene.js')]);
 const game=new Phaser.Game({type:Phaser.CANVAS,parent:'app',width:480,height:800,pixelArt:true,roundPixels:true,backgroundColor:'#090b15',scale:{mode:Phaser.Scale.FIT,autoCenter:Phaser.Scale.CENTER_BOTH},dom:{createContainer:true},render:{antialias:false,pixelArt:true},scene:[BootScene,TitleScene,CharacterCreateScene,GameScene]});
 if(import.meta.env.VITE_E2E==='1')window.__GDA__=game;
}
boot().catch(error=>{document.getElementById('app').textContent='起動に失敗しました。再読み込みしてください。';console.error(error);});
if('serviceWorker' in navigator && import.meta.env.PROD)navigator.serviceWorker.register('./service-worker.js').catch(console.error);
