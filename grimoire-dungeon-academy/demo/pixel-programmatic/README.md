# GDA Programmatic Pixel Hero Demo

`index.html` だけで動く、Grimoire Dungeon Academy 用のプログラム生成ドット絵検証版です。

## 実装内容

- 32×32 RGBA バッファを `set(x, y, color)` で 1 ピクセル単位に生成
- 外部 PNG / ライブラリなし
- 4方向
- 6フレーム歩行
- A: idle（魔導書を胸前）
- B: walk（左手に魔導書）
- C: cast（魔導書を開いて前方へ）
- 属性差し替え: Arcane / Fire / Ice / Lightning / Dark / Light
- WASD / 矢印 / タッチ十字キー
- Space / CAST で詠唱
- Q で属性切替

## 起動

そのまま `index.html` をブラウザで開けます。ローカルHTTPでも動作します。

この検証が採用になれば、同じ `PixelSprite` / レイヤー方式を本体の `CharacterRenderer` に移植します。
