# PRISM 2026-11-09 22時台 結果照合・学習監査 v1
classification: POST_RACE_RETROSPECTIVE (NOT PRE_FORECAST)
audit_time_jst: 2026-11-09 22時台
character_db: https://app.notion.com/p/e4615cdcad494bf7a177c7708b5fe627
character_db_status: 20 rows read directly; 1 editor, 1 reporter, 18 specialists; unverified personality fields not promoted.
independent_ai_runs_this_audit: 0

## 名古屋11R NAR-20261109-24-11
pre_source: prism/runs/2026-11-09/nagoya-11-editorial-draft-v1-1507.md (GitHub blob 4dcbf7a68278e2afeeffa1876c9c06296d0a4953)
pre_status: PRE_RACE_EDITORIAL_DRAFT_NOT_INDEPENDENT, saved_at null; time authenticity not yet confirmed
pre_marks: ◎7 トッピゴー / ○6 グランドネビュラ / ▲5 ユアグローリー / △9 マフィン / ☆11 マイネルモンテュス
pre_bets: 馬複7-6,7-5,7-9; ワイド7-11; 三連複5-6-7; each 100 JPY (500 JPY)
result: 1着7 トッピゴー / 2着8 ジェットブレイク / 3着3 スティルアローン
result_source: https://keiba.rakuten.co.jp/race_performance/list/RACEID/202611092433160111
refund_source: https://keiba.rakuten.co.jp/race_dividend/list/RACEID/202611092433160110
retrospective_virtual_settlement: stake 500 JPY, refund 0 JPY, P/L -500 JPY, hit 0/5
settlement_scope: editorial draft ONLY; exclude official independent-AI metrics and unverified PRE count
analysis: ◎7 correctly won; 8 (second, 10th favorite) and 3 (third) were unmarked. Top-three coverage failed. The winning 7-8 quinella paid 18,740 JPY per 100 JPY, but was not purchased; no hindsight credit.

## 盛岡11R NAR-20261109-10-11
pre_report: ◎12 ソラーロ / ○3 プリンスミノル, virtual 500 JPY; pre version timing still needs GitHub provenance validation.
result: 1着3 プリンスミノル / 2着12 ソラーロ / 3着11 ラティサワー
result_source: https://nar.netkeiba.com/race/result.html?race_id=202635110911
settlement: HOLD pending official refund and verified original full bet list.

## 川崎11R NAR-20261109-21-11
pre_source: prism/runs/2026-11-09/kawasaki-11-editorial-pre-v1-1906.md
pre_bets: 馬複2-9,6-9,9-12; ワイド4-9; 三連複2-6-9, 100 JPY each
result_partial: winner 10 タイセイミッション, source https://nar.umanity.jp/racecard_result.php?race_id=2026110921090111
settlement: HOLD until full top-three and official refunds; no zero refund assumption.

## 佐賀11R NAR-20261109-32-11
pre_source: prism/runs/2026-11-09/saga-11-editorial-official-field-pre-v3-1904.md
pre_bets: 馬複8-11,4-8,8-10; ワイド4-11; 三連複4-8-11,8-10-11, each 100 JPY
settlement: HOLD, result/refund not reliably obtained in this audit.

## QA and outstanding
- No independent expert forecast or completed five-topic debate in this run.
- PRE editorial drafts must not count as fully verified official independent forecasts.
- No forecast files changed after start; this is a separate append-only retrospective.
- Next: official results and refunds for Saga/Kawasaki/Morioka, verify GitHub commit times, persist per-predictor settlement, CI and Notion progress.
