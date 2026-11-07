# EVALS

Every phase passes its gate before the next starts.

- Tiers: **CRITICAL** (must pass; auto-fix loop, max 3 tries, then stop with root cause + 2 options), **PASS** (must pass), **GOOD** (target; miss = WARN, non-blocking).
- Gate OPEN = all CRITICAL + PASS pass.
- Run: `make evals PHASE=N` (one gate), `make evals` (all). Unit tests: `make test`.
- Scorecards: `evals/results/phaseN.json` + `phaseN.md` (check | tier | value | threshold | status).
- Tests read real data in `data/` and real network. No mocks of pipeline output.
- Thresholds are fixed. Changes need user approval + a DECISIONS.md row.

## Phase 0: Audit + plan (`tests/evals/test_phase0_audit.py`)

| check | tier | threshold |
|---|---|---|
| Audit table (AUDIT.md) covers 100% of files at commit `81a5e8e` with keep/adapt/archive | CRITICAL | 100% |
| Zero deletions vs `81a5e8e` (git diff -M, every original blob still tracked) | CRITICAL | 0 |
| PLAN.md must-have hours fit 2-day budget | PASS | <= 12 h (2 x 6 h floor) |
| Must-have vs stretch split: columns, every phase has must-have, stretch priority list | GOOD | all true |

## Phase 1: Ingest (`tests/evals/test_phase1_ingest.py`)

| check | tier | threshold |
|---|---|---|
| Historical seasons loaded | CRITICAL | >= 6 |
| Every scheduled GW present per season (vs fixtures; 2019/20 GW39-47 mapped to 30-38); live: every finished GW | CRITICAL | all seasons |
| Rerun ingest = identical row counts + parquet hashes (2 forced runs) | CRITICAL | 0 differ |
| Raw saved as parquet in data/raw/, rows match manifest, no stray CSV | CRITICAL | 0 bad |
| Live API: bootstrap-static, fixtures, element-summary, event live return data (uncached calls) | CRITICAL | all 4 |
| Rate limit >= 1 s per host + disk cache hit with network disabled | CRITICAL | >= 1.0 s, hit |
| Snapshot current GW = live FPL site current GW | PASS | equal |
| Players per season in plausible range; outliers flagged at abs(z) > 1.5 | PASS | 550-950 |
| xG/xA non-null coverage in seasons where source has it (2022-23+, live) | GOOD | >= 0.90 |
| Data source choice justified in DECISIONS.md | GOOD | row + reason > 40 chars |

## Phase 2: Clean (`tests/evals/test_phase2_clean.py`) DRAFT, awaiting approval

Contract: `data/interim/player_gw.parquet`, one row per (player_id, season, gw, fixture) with season, gw, player_id, code, element, fixture, team, opponent_team, position, total_points, minutes, first_name, second_name, web_name, player_status (returning / moved_pl_club / new_to_pl), promoted_team.

| check | tier | threshold |
|---|---|---|
| Duplicate (player, season, GW, fixture) keys | CRITICAL | 0 |
| Nulls in total_points, minutes, team, position | CRITICAL | 0 |
| Points per (season, element, GW) reconcile to raw (exact duplicate raw rows dropped; live = finished GWs) | CRITICAL | 100% |
| Returning players (same `code` in consecutive seasons) share one player_id | PASS | >= 98% |
| Same, stretch target | GOOD | >= 99.5% |
| 10 known players spot-checked: Salah, Rice (mover), Haaland (new), Havertz (mover), Palmer (mover), Ødegaard (accent), B. Fernandes, Son (raw name order flips), Mitrović (gap season + promoted), Gyökeres (new, accent) | GOOD | 10/10 |

## Phases 3 to 6: PROPOSED (tests written at start of each phase, after approval)

### Phase 3: Features

| check | tier | threshold |
|---|---|---|
| Leakage: recompute features for 200 random (player, GW) with all data >= GW removed; identical | CRITICAL | 100% equal |
| Target GW stats never in features (column audit vs same-row raw) | CRITICAL | 0 leaked cols |
| Rolling 3/5/10 values match hand calc on 20 sampled players | CRITICAL | 100% |
| Cold-start rows (games_played_in_PL < 3) have prior-filled features | PASS | 100% non-null |
| games_played_in_PL monotone non-decreasing per player | PASS | 100% |
| Rolling-5 points Spearman with next-GW points (sanity) | GOOD | >= 0.30 |

### Phase 4: Model

| check | tier | threshold |
|---|---|---|
| Season split: train 2019-20..2023-24, val 2024-25, test 2025-26, no overlap | CRITICAL | 0 overlap |
| LightGBM 1 GW MAE on test beats rolling-avg baseline | CRITICAL | lower |
| Live predictions: every available player, 3 horizons, no NaN, confidence flag | CRITICAL | 100% |
| LightGBM Spearman on test vs FPL xP baseline | PASS | >= baseline - 0.02 |
| Metrics table covers every model x horizon x segment (returning / new) | PASS | 100% |
| Top-10 hit rate by position beats rolling-avg baseline | GOOD | >= +5 pts |
| DL model shipped only if it beats GBM on test | GOOD | rule held |

### Phase 5: Recommender

| check | tier | threshold |
|---|---|---|
| Every output squad valid: £100m, 2/5/5/3, <= 3 per club, valid XI formation, 1 C + 1 VC | CRITICAL | 100% on 200 random scenarios |
| Transfers respect bank + free transfers; -4 per extra transfer applied | CRITICAL | 100% |
| ILP solve time per call | PASS | < 10 s |
| Chip timing flags DGW/BGW correctly on 2025-26 schedule | PASS | 100% |
| Backtest on 2025-26 vs baseline (rolling-avg picks) | GOOD | >= baseline points |

### Phase 6: App + refresh

| check | tier | threshold |
|---|---|---|
| `make refresh` end-to-end exit 0 | CRITICAL | exit 0 |
| Streamlit AppTest: every tab renders, no exception, for a real team ID | CRITICAL | 0 exceptions |
| Accented names render and are selectable (Ødegaard, Gyökeres) | CRITICAL | 100% |
| Warm-cache refresh time | PASS | < 15 min |
| README steps reproduce in clean venv | GOOD | pass |
