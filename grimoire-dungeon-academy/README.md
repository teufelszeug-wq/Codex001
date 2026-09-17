# Grimoire Dungeon Academy (GDA)

iPhone Safari / PWA と Windows ブラウザ向けの、魔導書切替型ターン制2DローグライクRPG。

## 縦切り版で実装済み
- タイトル / 新規ゲーム / CONTINUE
- 名前自由入力 + プリセット
- rot.js Diggerによるランダムダンジョン
- FOV / 探索済みマップ
- 32px SD主人公をコード描画（黒髪ロング・ジト目・紺×金）
- 正面/左右/背面 × 歩行6フレーム、待機A、通常歩行B、詠唱準備C
- スライム / スケルトン + A*追跡
- 闇 / 炎 / 光の魔導書3冊を装備切替
- 魔法攻撃、属性倍率、MP、EXP、レベルアップ
- B1F 学園地下 → B2F 図書館迷宮（以降テーマ循環）
- localStorageセーブ（位置も保存）
- PCキーボード + スマホ画面ボタン
- PWA manifest / 本番ビルド用オフラインService Worker

## 必要環境
- Node.js 20以上（依存パッケージのインストール不要）
- 初回PWAインストール時のみネット接続（Phaser 3.90.0 / rot.js 2.2.1を固定CDNから取得してキャッシュ）

## 開発
```bash
npm run dev
```
ブラウザで `http://localhost:4173` を開く。

## テスト / 構文確認 / ビルド
```bash
npm test
npm run check
npm run build
```

## 操作
PC: WASD / 矢印=移動、Space/Enter=魔法、Q=魔導書、P=セーブ。
スマホ: 画面下の方向/Cast/Book/Saveボタン。

## iPhone PWA
1. `npm run build`
2. `dist/` をHTTPSの静的ホスティング（GitHub Pages等）へ配置
3. iPhone Safariで開く
4. 共有 → ホーム画面に追加

## ライブラリ
- Phaser 3.90.0（固定）
- rot.js 2.2.1（固定）

## Procedural 96x96 heroine engine (development branch)

The heroine is now generated from code and data rather than a finished PNG sprite sheet. The procedural pipeline is:

`HeroSpec -> Pixel primitives -> Rig/anchors -> Pose/Motion LUT -> Direction layer order -> 1px correction patches -> 96x96 PixelSurface -> Phaser CanvasTexture cache`

Source modules live in `src/rendering/procedural/`. Walk frames are generated for four directions with six frames each. Idle and cast-preparation poses plus grimoire element palette variants are generated through the same pipeline. The game uploads generated frames once (boot/equipment change) and uses cached Phaser textures during play.

Run `node scripts/export-procedural-hero.mjs <output-dir>` to export PPM preview frames without any browser or image dependency.

## Procedural heroine engine (96x96)
The heroine is generated from code/data rather than stored as a finished sprite sheet. `HeroSpec` controls appearance/equipment, `HeroMotion` supplies integer-grid pose algorithms, `HeroGenerator` rasterizes layered body/hair/outfit/weapon/magic parts, and `PhaserHeroTextureAdapter` caches generated frames as Phaser CanvasTexture atlases.

Current variation hooks:
- Hair: `longStraight`, `bob`, `ponytail`
- Outfit: `academy`, `robe`, `archmage`
- Palette: `default`, `emerald`, `crimson`, `ivory`
- Equipment weight: `light`, `medium`, `heavy`
- Weapon type: `grimoire`, `staff`
- Elements: dark, fire, ice, lightning, light, arcane, wind, star

Generated motions: idle, 4-direction walk (6 frames), cast prep, cast, release, dash, jump, landing, damage, fallen, recovery, pickup, inspect, open door, and sit.
