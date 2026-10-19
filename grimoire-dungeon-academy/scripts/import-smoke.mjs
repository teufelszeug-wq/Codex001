globalThis.Phaser={Scene:class{},Display:{Color:{}},Scale:{FIT:1,CENTER_BOTH:1},AUTO:1};
globalThis.ROT={};
const files=[
'../src/scenes/BootScene.js','../src/scenes/TitleScene.js','../src/scenes/CharacterCreateScene.js','../src/scenes/GameScene.js',
'../src/core/GameState.js','../src/core/SaveManager.js','../src/core/TurnManager.js','../src/core/RNG.js',
'../src/dungeon/DungeonGenerator.js','../src/dungeon/FOVSystem.js','../src/dungeon/FloorTheme.js',
'../src/entities/Player.js','../src/entities/Enemy.js','../src/combat/CombatSystem.js','../src/combat/MagicSystem.js','../src/combat/ElementSystem.js',
'../src/items/ItemDatabase.js','../src/items/EquipmentSystem.js','../src/items/GrimoireDatabase.js',
'../src/rendering/PixelRenderer.js','../src/rendering/CharacterRenderer.js','../src/rendering/EquipmentRenderer.js','../src/rendering/MagicEffectRenderer.js',
'../src/ui/HUD.js','../src/ui/MobileControls.js','../src/ui/MessageLog.js'];
for(const f of files) await import(new URL(f,import.meta.url));
console.log(`module import smoke OK: ${files.length}`);
