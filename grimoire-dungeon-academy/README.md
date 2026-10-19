# Grimoire Dungeon Academy

グリモア・ダンジョン・アカデミー v0.1.4。既存 v0.1.3-dev の96×96手続き生成キャラクターを継承した、ターン制ローグライクの地下実習版です。

## 今回の修正

- CSSの直接importと `import.meta.env` が素のブラウザで失敗していた起動経路を、Viteによるビルドへ統一。
- Phaser 3.90.0 / rot.js 2.2.1 / 日本語フォントを同梱。実行時CDN通信を廃止。
- ループ詠唱でターンが永久ロックされる不具合を修正。詠唱準備→詠唱1周期→発動→待機。
- セーブにマップ・敵の残HP/死亡・探索済みマス・ターン数を追加。旧セーブは読み込み可能。
- 敵の重複配置、保存例外、行動中の魔導書切替、範囲外の探索座標を修正。
- WAITでMP回復、対象選択、支給ローブ3種類の変更、B2F出口の実習修了画面。

## Windowsで起動

Node.js 20.19以上を使用。

```powershell
npm ci
npm run dev
```

表示されたlocalhost URLを開きます。ソースを編集すると反映されます。

```powershell
npm test
npm run lint
npm run check
npm run build
npm run preview
```

配布ZIPにはビルド済み `dist/` も含みます。ZIPを展開して `START_GAME.cmd` を実行すると、Node.jsのみで起動できます。HTMLファイルのダブルクリックではなくHTTPで開いてください。

## 操作

| 操作 | PC | スマホ |
|---|---|---|
| 移動 | WASD・矢印 | 方向ボタン |
| 魔法 | Space・Enter | CAST |
| 魔導書変更 | Q | BOOK |
| 待機・MP+3 | . | WAIT |
| 対象切替 | Tab | 対象ボタン・敵をタップ |
| ローブ変更 | R | ROBE |
| 保存 | P | SAVE |

移動・魔法・待機・装備変更は1ターン。壁への入力は消費しません。行動終了時に自動保存します。階段へ移動するとB2Fに進み、B2Fの階段で実習修了です。闇・炎・光の魔導書と、学園制服・蒼き魔法衣・星辰のローブを実習用に支給しています。

## iPhone PWA

`dist/` をHTTPSで配信し、Safariの共有メニューから「ホーム画面に追加」。初回は通信が必要です。Service Workerの全ファイル保存が完了した後はオフラインで起動できます。Windowsの `http://192.168...` への接続ではHTTPS要件を満たさず、PWAのオフライン機能は検証できません。

セーブは端末・ブラウザごとです。ブラウザのデータ削除や保存領域の消去で失われます。

## 開発の正本と履歴

GitHub: `teufelszeug-wq/Codex001` の `grimoire-dungeon-academy/`。
元資料: `Grimoire_Dungeon_Academy_v0.1.3-dev_source_with_git.zip`、基準コミット `7c252fc`。
このZIPのGit履歴から直接修正しています。配布ZIPの `git-history.bundle` に以前のコミットも収録。`git clone git-history.bundle restored-gda` で復元できます。

## 検証と残りの範囲

`docs/VALIDATION.md` に実施したテスト、`docs/RESEARCH.md` に技術調査と判断を記録。

これは地下実習版です。9属性すべての戦闘、ショップ、罠、イベント、持ち物画面、ストーリー、B3F以降の攻略は未完成です。生成できるアニメーションとゲーム中に接続済みのアニメーションは異なります。髪型・パレット・武器・重量の生成機構は維持していますが、ゲーム内の選択画面はまだありません。

iPhone実機Safariでの最終確認とHTTPS公開は別途必要です。Chromiumのモバイル相当検証を実機テストと同一視しません。
