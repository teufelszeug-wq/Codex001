# PRISM POST official settlement — 2026-11-08 帯広11R クインカップ
race_id: NAR-20261108-OBI-11
status: POST_OFFICIAL_SETTLED
pre_snapshot: prism/runs/2026-11-08/obihiro-11-queen-cup-pre-conversation-1951.md
pre_snapshot_captured_at_jst: 2026-11-08T19:51:18+09:00
official_results_source: https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RefundMoneyList?k_babaCode=3&k_raceDate=2026%2F11%2F08&k_raceNo=11
official_result: 1st 2 ホクセイヒラリ; 2nd 7 ホクショウサクラ; 3rd 5 パワフルクィーン
winning_bets: 馬連複 2-7 1020円; 馬連単 2-7 1170円; 三連複 2-5-7 3250円; 三連単 2-7-5 9180円 (per 100円)
source_type: NAR official post-race results
actual_ticket_purchase_confirmed: false
pre_independent_ai_runs_confirmed: false

## Exact settlement against frozen PRE snapshot (100 yen each)
Main editorial 8 tickets:
- 馬複 2-4: 0円
- 馬複 2-9: 0円
- 馬複 4-9: 0円
- 馬単 2→4: 0円
- 馬単 4→2: 0円
- 3連複 2-4-9: 0円
- 3連複 2-3-4: 0円
- 3連複 2-4-10: 0円
Main: 800円 stake, 0円 return, -800円 net, 0% ROI, 0/8 tickets.

りお viewpoint 4 tickets:
- 馬複 4-2: 0円
- 馬複 4-9: 0円
- 馬単 4→2: 0円
- 3連複 2-4-9: 0円
りお: 400円 stake, 0円 return, -400円 net, 0% ROI, 0/4 tickets.

Combined: 1200円 stake, 0円 return, -1200円 net, 0% ROI, 0/12 tickets.
No refund was observed for these specific tickets on official published result; final refund exception not separately audited. Simulated ticket accounting, not verified real monetary loss.

## Retrospective diagnosis (not a PRE prediction)
- Main ◎2 ホクセイヒラリ correctly identified winner, but excluded 2nd 7 ホクショウサクラ and 3rd 5 パワフルクィーン from all 8 tickets.
- りお ◎4 フジエース did not win; her tickets also excluded 7 and 5.
- Strong favorite concentration 2/4/9 was not robust against 7/5 placing.
- Improve per-horse risk assessment for 7 and 5 before next race: race conditions, prior head-to-head, weight, track moisture, second-obstacle performance, and whether the market understates their place chances.
- Do not attribute precise cause to obstacle/trip without verified race replay; do not backfill any new pre-off pick.
- Agent character profiles are not fully verified from Notion, so no invented character dialogue or independent AI performance.

## Next-run operational priority
2026-11-09 NAR 11R schedule (official NAR pages): 盛岡11R 17:40 12 horses, 名古屋11R 18:20 11 horses, 佐賀11R 20:05 12 horses, 川崎11R 20:15 12 horses. Also 盛岡12R 18:15 and 佐賀9R 19:00 are major classes. Check cancellations and named all-horse entries before pre-off predictions.
Official schedule sources:
https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceList?k_babaCode=10&k_raceDate=2026%2F11%2F09
https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceList?k_babaCode=24&k_raceDate=2026%2F11%2F09
https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceList?k_babaCode=32&k_raceDate=2026%2F11%2F09
