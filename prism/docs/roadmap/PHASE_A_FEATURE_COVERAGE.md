# Phase A Feature Coverage Census v0.1

This is a source/contract coverage census, not a claim that January row-level values are recovered.

| Feature family | Canon contract | Source route | January recovery | Temporal risk |
|---|---|---|---|---|
| race identity/date/venue/race no | YES | JRA/NAR official | PARTIAL via reports | low-medium |
| surface/distance/class | YES | JRA/NAR official | PARTIAL | low |
| runner/horse no/frame | YES | official racecard/result | NAR runner raw NOT_RECOVERED | medium |
| jockey/trainer/carried weight | YES | official | raw NOT_RECOVERED | medium |
| finish/time/margin/corner/last3f | YES | official results | research artifacts exist | POST_ONLY for prediction |
| weather/going | YES | official | partial | timestamp dependent |
| body weight/delta | YES | official | raw NOT_RECOVERED | timestamp dependent |
| odds/market | SEPARATE STORE | official/authorized route | January PIT not certified | high |
| workout | YES | source-specific | NOT_RECOVERED | high |
| comments | YES | source-specific | NOT_RECOVERED | high |
| pedigree | YES | official/authorized route | NOT_RECOVERED | low-medium |
| course geometry | YES | static reference | design route exists | low |
| pace projection | DERIVED | feature engine | NOT_REPRODUCED | input dependent |
| TBI/SSI | DERIVED | same-day evidence | NOT_REPRODUCED | high |
| video annotation | DERIVED | permitted video | NOT_REPRODUCED | rights+timestamp high |

## Gate
Phase B may start B0 with recovered and temporally classified inputs. Full PRISM B11 requires required feature families or explicit masking with coverage-matched evaluation.
