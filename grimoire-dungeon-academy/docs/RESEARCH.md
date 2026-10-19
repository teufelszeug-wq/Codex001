# GDAの起動・PWA・継続開発に関する技術調査

## 結論

v0.1.3の96px手続き生成エンジンを維持し、配信経路とターン終了・保存処理を修正する方針を採る。描画を作り直すより、再現可能なビルドと実ブラウザ検証を先に確立する必要がある。今回の公開可能な単位はB1F〜B2Fの地下実習版であり、長期仕様全体の完成ではない。

## 既存実装の監査

既存のbuild.mjsはファイルをコピーするだけだった。一方、main.jsはCSSをJavaScriptとしてimportし、素のブラウザに存在しないimport.meta.env.PRODを参照していた。構文チェックやモジュールのスタブによるimport確認だけでは、この実行上の失敗を検出できない。このため、ViteでCSSとJavaScriptをビルドし、Phaser・rot.jsもnpmの固定バージョンから取り込む。

Phaserはブラウザ向け2Dゲームフレームワークであり、Canvas/WebGL描画を提供する。JavaScriptのライブラリとして組み込む設計が公式に示されている。[1] 今回はCanvas描画と既存Phaserシーン構造を維持した。rot.jsはマップ生成、FOV、経路探索、乱数の機能を提供しており、既存採用を継続する根拠になる。[2]

## ターン処理とアニメーション

ゲームの行動完了を待つPromiseは必ず終了しなければならない。既存のcastアニメーションはrepeat=-1で登録される一方、ゲームシーンはanimationcompleteを待っていた。これは視覚上は動いていても、以後の入力をロックする不具合になる。

修正ではアニメーション資産のループ定義を消さず、戦闘中の再生時にrepeat=0を明示する。生成プレビューでのループ用途と、戦闘の一回再生を両立できる。ターン中の装備差し替えはアニメーションやテクスチャを破棄し得るため、移動・魔法と同じ排他処理を通す。

## 再開可能なセーブ

ダンジョンseedと主人公座標だけでは途中状態を復元できない。敵の死亡、残HP、探索済み視界など、生成後に変化した値を保存する必要がある。v0.1.4はマップと敵のスナップショット、探索済み座標、ターン数、実習状態を保存し、敵クラスの振る舞いを復元する。

localStorageは小さな状態を扱う今回の規模では簡潔だが、ブラウザ保存は永久保証ではない。保存領域はorigin単位で扱われ、制限到達や削除への対処が必要になる。[3] 例外時に成功表示を出さないこと、壊れたJSONを開始データとして採用しないことを検証する。クラウド同期と別端末への移行は今後の作業である。

## オフラインと更新

Service WorkerはHTTPS、またはローカル開発のlocalhostで使用する。[4] 初回に外部CDNへ依存すると、CDN到達性が起動とキャッシュ作成の前提になる。ライブラリと日本語フォントをdistへ同梱し、同一originの資産だけをまとめて保存する方式に変更した。

キャッシュ名はビルド済みファイル内容のハッシュから生成する。activate時に削除するのはgda-で始まるキャッシュだけとし、同一originの他アプリに影響しないようにする。更新時にskipWaitingを強制せず、旧画面と新JavaScriptが混在する可能性を抑える。ナビゲーションの失敗時だけindex.htmlを返し、JavaScriptやフォントの404をHTMLで隠さない。

## iPhoneの表示と入力

iPhoneの画面端にはsafe-areaへの配慮が必要であり、WebKitはviewport-fitとsafe-area-insetの使い方を示している。[5] 現在の縦画面480×800をFIT縮小する方式は既存互換性を優先した選択である。画面全域を細かく活用するレスポンシブUI、操作ボタンの大きさ、横画面、仮想キーボード表示中の配置は、実機で次に評価する。

Canvasに日本語文字を描く前にフォントの該当文字を読み込む。CSSのフォント宣言だけでは、最初のCanvas描画時に必要な字形が準備済みとは限らない。画面に存在する文言と入力された主人公名の読み込み完了を待つ。

## GitHubの統合

Codex001は他作品も置かれるリポジトリとなったため、ゲームをgrimoire-dungeon-academy/に配置する。回収したソースZIPのGit履歴は配布bundleで保持し、GitHubには基準版の取込みと修正版を別コミットで記録する。別作品のファイルやルートREADMEは変更しない。

GitHub PagesはブランチまたはGitHub Actionsを配信元に設定できる。[6] ビルド済みdistを配信する必要がある。HTTPS配信先の設定と公開結果を確認するまでは、想定URLを公開済みとして案内しない。

## 検証の意味と限界

純粋なロジックテストでは生成座標の重複と到達性、保存復元、排他制御を検証する。実ブラウザでは本物のPhaser初期化、名前入力、魔法の完了、セーブ復元、ローブ変更を通す。オフラインの確認は本番ビルドでService Worker制御を待って通信を切り、再読み込み後に行動して保存が更新されるところまで行う。

テスト用に階段や敵の状態を配置したケースは、自然なプレイだけで全経路を攻略した証明ではない。戦闘バランス、長時間のメモリ使用、iPhone Safari固有挙動は別の評価が必要である。詳細な実施結果と未検証事項はVALIDATION.mdを参照。

## 出典

1. Phaser Studio, [What is Phaser?](https://docs.phaser.io/phaser/getting-started/what-is-phaser)。参照日2026-09-12。
2. Ondřej Žára, [rot.js interactive manual](https://ondras.github.io/rot.js/manual/)。参照日2026-09-12。
3. MDN, [Storage quotas and eviction criteria](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria)。参照日2026-09-12。
4. MDN, [Using Service Workers](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API/Using_Service_Workers)。参照日2026-09-12。
5. WebKit, [Designing Websites for iPhone X](https://webkit.org/blog/7929/designing-websites-for-iphone-x/)。参照日2026-09-12。
6. GitHub, [Configuring a publishing source for your GitHub Pages site](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site)。参照日2026-09-12。
7. 既存成果物 `Grimoire_Dungeon_Academy_v0.1.3-dev_source_with_git.zip`、commit 7c252fc。コードと履歴をローカルで監査。非公開資料のため外部URLなし。
