const Phaser = globalThis.Phaser;
import './styles.css';
import { BootScene } from './scenes/BootScene.js';
import { TitleScene } from './scenes/TitleScene.js';
import { CharacterCreateScene } from './scenes/CharacterCreateScene.js';
import { GameScene } from './scenes/GameScene.js';

const config = {
  type: Phaser.AUTO,
  parent: 'app',
  width: 480,
  height: 800,
  pixelArt: true,
  roundPixels: true,
  backgroundColor: '#090b15',
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH },
  dom: { createContainer: true },
  render: { antialias: false, pixelArt: true },
  scene: [BootScene, TitleScene, CharacterCreateScene, GameScene]
};

new Phaser.Game(config);

if ('serviceWorker' in navigator && import.meta.env.PROD) {
  window.addEventListener('load', () => navigator.serviceWorker.register('./service-worker.js').catch(console.error));
}
