# 新聞発行から始める実行手順

`scripts/publish_newspaper.py` は新聞の発行要求から既存処理を呼び出す入口。
全専門AIの独立実行や本番運用全体の完成を宣言するものではない。

## 実行

Pythonパッケージの `paper` 追加依存、Node.js、Noto CJKフォントが必要。

```sh
python -m pip install './prism[research,paper]'
python prism/scripts/publish_newspaper.py \
  --race-id 20261123-JRA-TOKYO-11 \
  --history /absolute/path/history \
  --out /absolute/path/publications \
  --assets-manifest /absolute/path/startup-assets.json \
  --official-url 'https://www.jra.go.jp/JRADB/accessD.html?CNAME=OFFICIAL_RACECARD' \
  --model auto
```

公式URLは対象レースの現物に置き換える。出馬表が保存済みなら省略可。
`--restore archive.zip` は既存の履歴復元処理を利用する。原本を上書きしない。

開始前にNotionの現行計画・人物DB、利用するGitHubコード、既存新聞・予想履歴を取得する。
この入口自体はNotionやLibraryのAPIクライアントではない。
取得した原本を次のmanifestに列挙すると、実行時に読み込み・SHA256照合を行い、
既存の名簿・役割定義・人物スナップショットと合わせて記録する。
最新取得の成否は呼び出し側が確認し、未取得を取得済みと報告しない。

```json
{"assets":[{"path":"/absolute/path/current-plan.txt","sha256":"実ファイルのSHA256","source":"取得元URLまたはID"}]}
```

`auto` は `OPENAI_API_KEY` と `PRISM_OPENAI_MODEL` が設定されている場合だけAPIを使う。
未設定時は既存の担当別ルール計算を使い、独立AI実行は0件と表示する。
専門入力不足は理由付き見送りにする。未確認の人物設定を作らない。
発走後に欠けている発走前予想を新規作成することは拒否する。

## 八項目と保存物

| 要件 | 実処理・証拠 |
| --- | --- |
| 既存資産を読む | `loaded-assets.json`：取得原本・ハッシュ・バイト数 |
| 新聞発行から処理を呼ぶ | 出馬表・予想・座談会が不足時に既存取得・予想バッチを実行 |
| 実行記録と予想原本を保存 | 履歴の `v1.json`、`v2.json`、`roundtable-v1.json` と `execution-originals.json` |
| 未実行AIを捏造しない | provider、実行ID、API response IDを区別。独立実行未確認は暫定版 |
| 全頭診断と座談会を掲載 | 全出走馬の本文、全担当の結論・見送り、保存済み5議題以上の本文 |
| 縦書き・馬名・本文を検査 | 縦組領域・フォント字形・全馬名・全文・ページ外文字の検査 |
| PNGとPDFの実体確認 | 開き直し・非空白・PDF再描画とのPNG画素一致・SHA256・全ページ目視 |
| 未完了の工程等を保存 | `publication-state.json` に原因・失敗工程・再開コマンド、各attempt原本 |

縦組の正確な文字組版からPDFと全ページPNGを作成する実装。
画像生成でPNGを先に作る制作手順を別途指定されたタスクについては、その順序を省略しない。
本実装だけでその画像生成手順を履行済みとは扱わない。

座談会の本文は保存原本を掲載するが、現在の担当別ルール計算に基づく座談会は
「編集部自動編集」であり、各AIの独立した実発言ではないと明記する。

## 失敗・再開・目視確認

発行失敗時も `publication-state.json` とattempt別のコマンド・失敗記録を保存する。
保存された `resume_command` を実行する。予想の再生成はせず、原本があれば再利用する。
再開ごとの検査フラグを初期化し、古い合格判定を持ち越さない。
履歴や出馬表が途中で変わっていればハッシュ・版チェーン検査で止める。

自動検査成功時の状態は `PENDING_VISUAL_REVIEW`。全PNGを実際に開いて確認した後、
対象editionを指定して目視結果を記録する。

```sh
python prism/scripts/publish_newspaper.py \
  --race-id 20261123-JRA-TOKYO-11 \
  --history /absolute/path/history --out /absolute/path/publications \
  --resume /absolute/path/edition \
  --visual-review '実際に確認した内容と残る問題' \
  --reviewed-pages 1,2,3,4,5,6 --reviewer reviewer-name
```

全ページ指定と成果物のハッシュを再確認する。未実行AIがある版は
`PROVISIONAL_PUBLISHED` に留める。紙面の完了とPRISM全体の完成は区別する。

## 今回の実行結果

2026年11月23日東京11R：公式出馬表12頭、初回と座談会後の担当別記録各19件、
5議題の編集部自動編集座談会、6ページPDF・PNG6枚を作成し目視確認した。
独立API実行0件、状態 `PROVISIONAL_PUBLISHED`。
原本照合の最初の失敗は埋め込みCJKフォントの互換文字表記による不一致。
比較時だけUnicode互換表記を正規化し、保存済み予想を変更せず再開した。

検証：Node 45件、新規発行試験3件、関連Python既存試験36件が成功（計84件）。
新規試験は開始資産の欠損、発走後の欠けた予想の作成拒否、
描画中断後の再開・原本保持・実PDF/PNG検査・部分目視申告と改変成果物の拒否を確認。
実レース検証は上記1R。全レース実運用、独立AI接続、公式精算、学習の完了は認定しない。
GitHub Actionsは今回の変更では未実行。リポジトリ全体の全試験成功も主張しない。

## 2026年11月24日：実行区分の訂正

紙面の集計はproviderから独立API実行0件と表示していたが、
旧生成コードではlocal_rulesの予想原本にもindependent_execution=trueが付いていた。
今後の新規ルール計算はmode=local_rule_calculation、independent_execution=falseとし、
保存台帳もEDITORIAL_PROVISIONALにする。local_rulesが独立実行を主張する新規保存は拒否する。
API予想の独立実行区分は維持する。発走前の既存原本、ハッシュ、PDF、PNGは書き換えない。
既存資料の訂正は原本とは別記録で保持する。
