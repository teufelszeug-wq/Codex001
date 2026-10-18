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
