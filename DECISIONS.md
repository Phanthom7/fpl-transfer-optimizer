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
| 25 | 2026-11-07 | 2 | player_id = FPL player `code`; team identity = FPL team `code`; canonical team name = latest season's name (e.g. "Ipswich Town") | Both codes stable across seasons; names change |
| 26 | 2026-11-07 | 2 | Row team derived from fixture (team_h/team_a + was_home), validated against opponent_team | Exact for mid-season movers; players_raw only has end-of-season team |
| 27 | 2026-11-07 | 2 | 2019-20: 59 rows for Arsenal v Man City listed under GW29 (postponed, 0 min, 0 pts) kept with `is_ghost_fixture=True`; real match at GW30 (raw 39). Downstream excludes ghost rows | Keeps 1:1 reconcile with raw; flag removes them from features |
| 28 | 2026-11-07 | 2 | 2024-25 Assistant Manager rows (position AM, 322 rows) kept with position "AM"; excluded from model/optimizer | Real raw rows with points, not players |
| 29 | 2026-11-07 | 2 | "GKP" normalised to "GK" | Label drift in 2021-22 |
| 30 | 2026-11-07 | 2 | player_status per season: new_to_pl = not in previous season's FPL player list; else returning if main club (most GW rows) = previous season's last club, else moved_pl_club. Season descriptor (uses full season), NOT a model feature; Phase 3 builds leak-free row-level equivalents | Palmer 2023-24 played GW1-3 for City; first-club rule mislabelled him |
| 31 | 2026-11-07 | 2 | 2018-19 players_raw ingested (aux) for 2019-20 status + promoted flags | Need previous season |
| 32 | 2026-11-07 | 2 | promoted_team = team code absent from previous season's team list | Simple, exact |
| 33 | 2026-11-07 | 2 | Live season: only finished GWs (1-9) in player_gw. Missing minutes: none found (0 nulls); no imputation done | GW10 in progress |
| 34 | 2026-11-07 | 2 | Price = value / 10 per row (price changes kept per GW). xG/defensive stats NaN where source lacks them (pre-2022, pre-2025); xP NaN for 2019-20 and live | Model handles NaN; no fake zeros |
| 35 | 2026-11-07 | 2 | User request: split status + add role + time at club. `status_detail` = returning / moved_pl_club / returned_to_pl (played PL minutes in a season before the previous one) / new_promoted_club / new_signing (first price >= 4.5 GK/DEF, >= 5.0 MID/FWD) / new_fringe. Coarse `player_status` kept for the eval contract | Finer cold-start segments |
| 36 | 2026-11-07 | 2 | `appearance` per match: started if starts >= 1 OR minutes >= 60; sub_on if 1+ min; else unused | `starts` missing pre-2022-23, only 64% filled in 2022-23 |
| 37 | 2026-11-07 | 2 | `role` (leak-free, previous 5 matches across clubs/seasons): starter if started >= 60%, substitute if appeared >= 40%, else benchwarmer; unknown with no history | Model-safe; role separates pts 2.76 / 1.40 / 0.18 |
| 38 | 2026-11-07 | 2 | `role_season` (descriptive, whole season): starter >= 50% started, substitute >= 25% appeared. Looser than rolling: injury/ban absences not visible (Mitrović 2022-23 started 22/38) | No historical injury data |
| 39 | 2026-11-07 | 2 | Tenure: `gws_at_club` (previous fixtures at club), `apps_at_club`, `days_at_club`; spell resets on club change, continues across gap seasons (e.g. relegated with club). `club_tenure_censored` = spell started before 2019-20 (true tenure longer) | Data starts 2019-20 |
| 40 | 2026-11-07 | 2 | Leak-free vs descriptive columns documented in src/clean/roles.py. Descriptive (appearance, role_season, status_detail, player_status) must not be model features as-is | Avoid leakage in Phase 3 |
| 41 | 2026-11-07 | cleanup | User instruction: remove everything stale/unused. Deleted `archive/` (legacy code, notebooks, 53 MB CSVs; recoverable from git 81a5e8e), `src/ingest/summary.py`, sample CSV, duplicate DQ report copy, `requests-cache` dep | Supersedes original "archive only, delete nothing" rule |
| 42 | 2026-11-07 | cleanup | Live season from FPL API only; vaastav 2026-27 mirror no longer ingested. Dropped unused raw tables: understat_player, master_team_list, event_live, element_types. API snapshot now one folder `data/raw/fpl_api/2026-27/`, overwritten each run (no dated copies). Player histories always pulled | One source per season, no stale copies. Pre-2022 xG stays NaN (no understat) |
