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
| 9 | 2026-11-07 | 0 | Current GW = 10 (2026-27), per user. Team ID deferred to model testing | User input |
| 10 | 2026-11-07 | 1 | Raw files per season: merged_gw, players_raw, fixtures, teams, understat_player (optional, season-level, 2019-20..2024-25 only) | All available from one source; understat gives pre-2022 xG at season level |
| 11 | 2026-11-07 | 1 | Encoding: try utf-8-sig, cp1252, latin-1; then NFC-normalise. Store strings as parquet `string` | 2019-20 understat is cp1252; NFC stops visually identical names differing in bytes |
| 12 | 2026-11-07 | 1 | Historical seasons are immutable once ingested (manifest present = skip). Live season re-fetched with 6 h cache TTL. `--force` overrides | Idempotent reruns, no needless traffic |
| 13 | 2026-11-07 | 1 | HTTP: 1 req/s per host, disk cache, 3 retries with backoff, stale cache used if network fails | Politeness + offline reruns |
| 14 | 2026-11-07 | 1 | vaastav 2026-27 mirror lags (GW1-6 only). Created personal env "fpl-transfer-optimizer" allowing fantasy.premierleague.com; API is primary for live season | Needed GW7-9 |
| 15 | 2026-11-07 | 1 | FPL API has no robots.txt (URL serves HTML app). Public read-only endpoints, 1 req/s, cached | ToS: personal, non-commercial use |
| 16 | 2026-11-07 | 1 | GW10 is in progress (not finished). Only finished GWs used for features/training. Next decision GW = 11 | Partial GW stats would leak/understate |
| 17 | 2026-11-07 | 1 | Understat/FBref scraping not done: hosts blocked and ToS restrictive. xG = FPL `expected_goals` (2022-23+) + vaastav understat season totals (2019-20..2024-25) | Avoid scraping; good enough coverage |
| 18 | 2026-11-07 | 1 | Prior-league stats for new signings: no reachable, ToS-safe source. Cold start uses priors (position x price x team) only. Stretch | Data unavailable |
| 19 | 2026-11-07 | E | Eval gate = all CRITICAL + PASS checks pass. GOOD misses = WARN, logged, non-blocking | Tier semantics |
| 20 | 2026-11-07 | E | Phase 0 budget check: must-have hours <= 12 h (2 days x 6 h floor of '6+ hrs/day'). PLAN revised: split Must/Stretch hrs, added eval row (was 12.5 h mixed) | Retro-eval failed at 12.5 h |
| 21 | 2026-11-07 | E | 'Every GW present' = every GW with scheduled fixtures in fixtures.csv. 2022-23 GW7 fully postponed (Queen's death), so absent by design | Real blank GW, not missing data |
| 22 | 2026-11-07 | E | 2019-20 GW39-47 mapped to 30-38 at ingest in new column `gw`; raw `GW` kept | Raw stays raw |
| 23 | 2026-11-07 | E | Player count plausibility range 550-950 per season; outliers flagged at abs(z) > 1.5 | No threshold given; set from FPL norms (600-870) |
| 24 | 2026-11-07 | E | Phase 2 reconcile drops exact duplicate raw rows first (2025-26 has 10). Not-exact (element, fixture) dupes in 2019-20 (59) must be resolved by Phase 2 code | Duplicate source rows are not real points |
