# Changelog

## 0.1.0 - 2026-09-13
### Added
- Playable vertical slice: title, character naming, B1F/B2F dungeon exploration, FOV, enemy AI, magic combat, grimoire switching, leveling, save/continue, mobile controls and PWA files.
- Programmatic 32px heroine renderer with four directions, six walk frames, idle-A and cast-prep-C poses.
- Three starter grimoires: Dark, Fire and Light.
- Two enemies: Slime and Skeleton.
- Floor themes for academy basement, library, laboratory and sealed zone.

### Changed
- Reworked project to run without `npm install`; Phaser 3.90.0 and rot.js 2.2.1 are pinned by CDN and cached by the production Service Worker.

## 0.1.1-dev
- Added a 96x96 algorithm-driven procedural heroine engine.
- Added integer-grid pixel primitives, rig anchors, discrete motion LUTs, direction-specific layer ordering and correction patches.
- Replaced 32x32 rectangle-based heroine generation with generated 96x96 cached CanvasTextures.
- Added procedural heroine tests and a browser-independent preview exporter.

## 0.1.3-dev - Procedural heroine variants and motion library
- Raised the 96x96 procedural heroine toward the approved long-black-hair / navy-gold academy-uniform reference.
- Added data-driven hair styles: long straight, bob, ponytail.
- Added outfit layers: academy, robe, archmage.
- Added palette variants and extended grimoire element palettes.
- Added equipment-aware motion profiles for light / medium / heavy gear and grimoire / staff weapons.
- Added generated motion library: idle, walk, cast prep, cast, release, dash, jump, landing, damage, fallen, recovery, pickup, inspect, open door, sit.
- Added CanvasTexture atlas upload and Phaser animation registration.
- Game casting now plays generated cast-prep / cast / release animations.

## 0.1.4 - 2026-09-17
- Preserve v0.1.3 procedural heroine implementation and history.
- Fix browser boot with Vite and local bundled runtime dependencies.
- Fix infinite casting wait by playing combat motions once.
- Save complete floor snapshots, explored cells, enemy HP/death and turns.
- Serialize equipment changes through the turn lock; add WAIT, target selection and robe changes.
- Add B2F completion; fix duplicate spawns and out-of-bounds FOV records.
- Preload Japanese glyphs before Canvas text rendering.
- Add regression/browser/offline tests and Windows prebuilt launcher.
