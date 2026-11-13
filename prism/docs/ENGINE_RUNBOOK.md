# 実験Core Engineの実行

Python 3.10以降、標準ライブラリのみ。B0の過去資料解析だけは旧runbookのlxml/Linux条件を参照。

```bash
cd prism
python3 scripts/verify_phase_b.py --out /path/to/new/audit
python3 scripts/run_core_engine.py --raw observations.json --market market.json --calibration calibration.json --locked-at 2026-01-01T09:55:00+09:00 --out /path/to/new/run
```

入力の最小例を作る正本は `tests/engine/fixture.py` の `observations_fixture()`、
`calibration_fixture()`、`market_fixture(lock)`。いずれも架空入力と明示している。
例の年月日は外部データ取得時刻ではない。

RAW JSONは `prism.engine.observations/v1`、正規化済みは `prism.engine.raw/v1`。
入力sourceはsource_id、available_at、payloadのSHA256を持つ。
`source.content_hash`はsource以外をsort_keys/UTF8/compact JSON化したhash。
sourceの真正性の外部保証は別。全ての日時はUTC offset必須。
horse_id、horse_no、frame_no、barrier_noは別値で、当初のbarrier_countをraceに保持する。

履歴のfinish_positionは過去走のみ。対象raceのresults/win_payouts/odds等は入力契約で拒否。
historyの発生と利用可能時刻、各workout/condition/jockey等の利用可能時刻は固定時刻より前が必要。
SYNTHETIC/歴史再構成/利用可能データという区分を省略しない。

Market JSONは予測lock_hashを参照し、opened_atは固定後、observed_atはopened_at以前。
券種ごとにlegsと下限/上限オッズを指定する。PLACEの着内数はauthorityに基づき明示する。
WINだけの逆オッズ正規化値は市場proxyであって真の確率ではない。
同一券の重複と枠連の馬ID混同は拒否する。

出力はbundle.json。prediction、確率、モジュール欠損、N-Value照合、市場値、買い目候補、
任意の精算を含む。再実行は同一内容だけ許容し、改訂は別ディレクトリに保存する。
結果JSONは完全な券種一覧と予想hashを含む必要があり、不足を外れとして黙って処理しない。

固定100円以外の実投票は行わない。SYNTHETIC bundleからの収益性評価も行わない。

## 各AIの発走前予想

Python 3.10以降、Node.js 22以降。リポジトリのルートで実行する。
公式出馬表のURLを渡し、JRAとNARのどちらかの取得コマンドを使う。

```bash
python3 -m pip install './prism[research]'

python3 prism/scripts/fetch_jra_racecard.py --for-forecast \
  --url "$PRISM_OFFICIAL_URL" --out ./racecard.json
# NARの場合
python3 prism/scripts/fetch_nar_racecard.py \
  --url "$PRISM_OFFICIAL_URL" --out ./racecard.json

node prism/scripts/run_forecast_panel.mjs --card ./racecard.json --out ./forecasts
```

- 発走前に取得した公式ページで、URLと開催日・場・競走番号を照合する。
  枠番・馬番・馬名は別々に記録する。取消・除外馬は買い目から外す。
- 本紙・りお・専門AI17名がそれぞれの担当分野で実行する。全出走馬の根拠と印を残し、
  買い目は仮想100円単位の単勝。資料が不足する場合は担当者ごとに見送り理由を残す。
  採点は公式出馬表からの簡易モデルで、既存のPhase B実験Core Engineの勝率や校正済み勝率とは別系統。
- `<race_id>/v1.json` が一次版、`v2.json` が五議題の比較を受けた最終版。
  最終処理に失敗した場合は同一入力で再実行して一次版から再開できる。
  実行ID、実行時刻、取得時刻、出典、版、保存時刻、前版のハッシュを保存する。
- 篠宮 律は司会の役割。五議題は一次予想の構造化比較で、会話形式の座談会本文は別途必要。
  `PRE_DAY` はレース日前の予想保存を示す。新聞の発行状態は新聞側で確認する。
- レース当日の取消・馬場等を受けた自動差分の発行、定期起動、M-PAPERへの投入、
  公式払戻の取得、予測精度の実測は予想コマンドの範囲外。

追加の評価資料は `--evidence` で渡せる。JSON配列の各行に `method`、`horse_no`、
`score`（0〜100）、`reason`、`source_url`（HTTPS）、`available_at`（タイムゾーン付き）を記録する。
`method` は `video`、`stable`、`pedigree`、`track_bias`、`weather`、`workout`、`learning`。
提供時点と対象馬を確認し、評価スコアの採点基準を理由に残す。

OpenAI Responses APIを使う場合は、実行環境のシークレットに `OPENAI_API_KEY` を、
環境変数に構造化出力対応モデルの `PRISM_OPENAI_MODEL` を設定し、コマンドに
`--model openai` を追加する。一次版は担当ごとの独立したリクエストで実行する。
最終版には各担当の一次予想と五議題の比較を渡す。各版にレスポンスIDを保存する。
