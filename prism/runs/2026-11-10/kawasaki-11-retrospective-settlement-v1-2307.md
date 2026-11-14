# PRISM RETROSPECTIVE — 川崎11R 富士見オープン（2026-11-10）
- race_id: NAR-20261110-21-11
- classification: RETROSPECTIVE_SETTLEMENT_DRAFT; NOT NEW PRE; NOT FORMAL INDEPENDENT_AI
- forecast_source: prism/runs/2026-11-10/kawasaki-11-editorial-pre-v1-2003.md (EDITORIAL_SINGLE_MODEL, v1)
- forecast_saved_at: GitHub commit timestamp still NOT independently verified against 20:15 JST; exclude from formal PRE statistics until checked
- result_source_official: https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?k_babaCode=21&k_raceDate=2026%2F11%2F10&k_raceNo=11
- payout_source_secondary: https://keiba.rakuten.co.jp/race_performance/list/RACEID/202611102100000011 (official payout page direct confirmation pending)
- result: 1st #10 ヒーローコール; 2nd #7 アルラ; 3rd #6 オピニオンリーダー
- change: #2 シンメルーブス jockey changed 篠谷葵 to 櫻井光輔 (secondary race page; official change confirmation pending)
## Original saved editorial selections, unchanged
- ◎ #6 オピニオンリーダー, ○ #4 マウンテンローレル, ▲ #8 ラッキードリーム, △ #10 ヒーローコール, ☆ #12 エクロジャイト
- 馬複 4-6 100円: lost
- 馬複 6-8 100円: lost
- 馬複 6-10 100円: lost
- ワイド 6-12 100円: lost
- 三連複 4-6-8 100円: lost
- stake 500 JPY; return 0 JPY; net -500 JPY; recovery 0% (provisional retrospective settlement)
- winning combinations: 馬複 7-10; ワイド 7-10,6-10,6-7; 三連複 6-7-10
## Learning observations
- #10 won despite being marked △; #7 (second) absent from top-five marks. Review weight penalty heuristic, distance suitability and pace; do not optimize retrospectively as if known pre-race.
- #6 third: central pick not winner. Pre-race model relied heavily on popularity; test probability calibration and underdog coverage on subsequent genuinely pre-saved races.
## QA and blockers
- This is a result-aware record. No retroactive prediction modifications. Do not count this as independently generated AI forecasts.
- Official payout direct read, actual commit timestamp comparison, and Notion DB row verification pending (Notion rate limited at run). Notion character database not edited.
