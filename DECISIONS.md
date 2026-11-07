# DECISIONS

Assumption log. Newest at bottom.

| # | Date | Phase | Decision | Why |
|---|---|---|---|---|
| 1 | 2026-11-07 | 0 | Archive all legacy code/data to `archive/`; port only optimizer + pitch rendering ideas later | Old pipeline built on name joins and notebook `exec`; data covered only 2016-18, 2020-24 |
| 2 | 2026-11-07 | 0 | Historical source: vaastav/Fantasy-Premier-League (GitHub) | Most complete public FPL archive, per-GW rows since 2016-17, includes FPL `xP`, xG/xA from 2022-23, `players_raw` with stable `code`; confirmed reachable |
| 3 | 2026-11-07 | 0 | Seasons: 2019-20 to 2025-26 (7) for training, 2026-27 live | Matches 6-7 season ask; 2019-20 needs GW remap |
| 4 | 2026-11-07 | 0 | Cross-season player key = FPL `code` (players_raw), never names | `element` ids change yearly; `code` is stable. Fixes accented-name bug |
| 5 | 2026-11-07 | 0 | Split: train 2019-20..2023-24, val 2024-25, test 2025-26 | Season-based, ~70/15/15 |
| 6 | 2026-11-07 | 0 | Live fallback: vaastav 2026-27 mirror when FPL API unreachable | API blocked in this sandbox (403) |
| 7 | 2026-11-07 | 0 | Model: LightGBM per horizon; DL only if beats GBM on test | Tabular data, small budget |
| 8 | 2026-11-07 | 0 | Storage: parquet (pyarrow) | Fast, typed, UTF-8 safe |
