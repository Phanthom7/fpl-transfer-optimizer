# System design: FPL Transfer Optimizer

Status: Phases 0 to 3 built and gated. Phases 4 to 6 designed here, not built.
Companion docs: `PLAN.md` (schedule), `DECISIONS.md` (assumption log), `EVALS.md` (quality gates).

## 1. Requirements

### Functional

| # | Requirement | Phase |
|---|---|---|
| F1 | Ingest 7 historical seasons + live season, rerunnable, cached | 1 (done) |
| F2 | One clean player-GW table across seasons, stable IDs, edge cases handled | 2 (done) |
| F3 | Leak-free features incl. cold start for new players / promoted teams | 3 (done) |
| F4 | Predict expected points (xPts) for next 1, 3, 5 GWs with a confidence flag | 4 |
| F5 | Recommend transfers (with -4 hit logic), captain + vice, XI + bench order | 5 |
| F6 | Build a squad from scratch; time Bench Boost and Free Hit | 5 |
| F7 | Streamlit app driven by a team ID; one-command refresh | 6 |

### Non-functional

| Quality | Target | Why |
|---|---|---|
| Correctness | No leakage (gated), no name-based joins | Past version broke on accented names |
| Freshness | Refresh before each GW deadline; a full refresh fits in a coffee break | Weekly decision cycle |
| Latency | App interactions < 2 s; one ILP solve < 10 s | Interactive use |
| Reproducibility | Same inputs = same outputs (hash-checked) | Trust the evals |
| Cost | $0: laptop, public data, open-source solver | Personal project |
| Politeness | <= 1 request/s to any host, disk cache, public endpoints only | Respect FPL + GitHub |

### Constraints and assumptions

- One user, one machine, runs locally. No server, no auth, no database.
- Data: vaastav/Fantasy-Premier-League (history) + official FPL API (live). No scraping.
- Public FPL endpoints only: no login, so selling prices and exact free transfers are not available (see 5.4).
- Budget: 2 days. Must-haves ship before stretch goals.

## 2. High-level design

```
                  ┌──────────────────────── refresh.py / make refresh ────────────────────────┐
                  │                                                                            │
 GitHub (vaastav) │   ┌──────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐    ┌────────────┐
 2018-19..2025-26 ├──►│  INGEST  ├───►│  CLEAN   ├───►│ FEATURES  ├───►│  MODELS  ├───►│ RECOMMENDER│
                  │   │ src/     │    │ src/     │    │ src/      │    │ src/     │    │ src/       │
 FPL API (live)   ├──►│ ingest   │    │ clean    │    │ features  │    │ models   │    │ recommender│
 2026-27          │   └────┬─────┘    └────┬─────┘    └─────┬─────┘    └────┬─────┘    └─────┬──────┘
                  │        ▼               ▼                ▼               ▼                ▼
                  │   data/raw/       data/interim/    data/processed/   models/        (in-process,
                  │   *.parquet       player_gw        features          *.txt +        called by app)
                  │                                                     predictions
                  └────────────────────────────────────────────────────────────────────────────┘
                                                                              │
                         FPL API (entry/{id}, picks)  ───────────────►  ┌─────▼──────┐
                         user's team, bank                              │ STREAMLIT  │◄── team ID,
                                                                        │ app/       │    FT, bank
                                                                        └────────────┘
 EVAL GATES (tests/evals) read every stage's output and block the next phase on failure.
```

Design principle: **batch pipeline of pure stages, files as contracts.** Each stage reads the previous stage's parquet and writes its own. Any stage can be rerun alone, tested alone and inspected in a notebook.

## 3. Components

| Component | Module | Input | Output | Status |
|---|---|---|---|---|
| HTTP layer | `src/ingest/http.py` | URL | bytes (disk cache, 1 req/s, 3 retries, stale-cache fallback) | done |
| Historical ingest | `src/ingest/historical.py` | vaastav CSVs | `data/raw/vaastav/<season>/{merged_gw,players_raw,fixtures,teams}.parquet` + manifest | done |
| Live ingest | `src/ingest/fpl_api.py` | FPL API | `data/raw/fpl_api/2026-27/{elements,teams,events,fixtures,element_history}.parquet` | done |
| Clean | `src/clean/` | raw | `data/interim/player_gw.parquet`, `reports/dq_report.md` | done |
| Features | `src/features/` | player_gw + raw fixtures/teams | `data/processed/features.parquet` | done |
| Models | `src/models/` | features | `models/lgbm_h{1,3,5}.txt`, `models/meta.json`, `data/processed/predictions.parquet`, `reports/model_report.md` | Phase 4 |
| Recommender | `src/recommender/` | predictions + user team | Python objects (squad, transfers, captaincy, chips) | Phase 5 |
| App | `app/streamlit_app.py` | predictions + FPL entry API | UI | Phase 6 |
| Orchestrator | `refresh.py`, `Makefile` | none | runs stages in order, stops on error | Phase 6 |
| Eval gates | `tests/evals/`, `evals/report.py` | every stage output | `evals/results/phaseN.{json,md}` | done (P0 to P3) |

## 4. Data model

All keys are numeric. Names are display-only.

| Entity | Key | Notes |
|---|---|---|
| Player | `player_id` = FPL `code` | Stable across seasons. `element` is per-season only |
| Team | `team_code` = FPL team `code` | Stable across seasons; display name = latest season's name |
| Gameweek | `(season, gw)`; time key `t = season_idx*100 + gw` | 2019-20 GW39-47 mapped to 30-38 |
| Fixture | `(season, fixture)` | DGW = 2 fixtures in one GW for a team |

### Tables

| Table | Grain | Rows | Key columns |
|---|---|---|---|
| `player_gw` | player x fixture | 191,844 | season, gw, player_id, fixture, team, opponent_team, position, total_points, minutes, xG/xA, price, role, tenure, status flags |
| `features` | player x GW (blank GWs filled; live GW10 to 15 added) | 194,968 | KEY + 86 features + targets `y_1, y_3, y_5` + `fpl_xp` baseline |
| `predictions` (P4) | player x target GW | ~4,000 (671 players x 6 GWs) | player_id, gw, xpts_1, xpts_3, xpts_5, xpts_gw (per-GW, for lineups/chips), confidence, availability |
| `model meta` (P4) | per horizon | 3 | feature list, train/val/test seasons, metrics, git commit, data hash |

### Column contracts

`src/features/spec.py` is the single source of truth for `FEATURES`, `TARGETS`, `CATEGORICAL`, `COLD_CORE`. Models, evals and the app import it; nothing re-lists columns.

## 5. Deep dives

### 5.1 Leakage control (built)

- Every history or team feature at GW g comes from `merge_asof(..., allow_exact_matches=False)` on the time key: only rows strictly before g.
- Allowed at g because they are known before the deadline: fixture list (FDR, home, opponent, next 3/5 GW counts), price at deadline, pre-season team strength.
- Ownership and transfers are lagged 1 GW.
- Descriptive columns (`appearance`, `role_season`, `status_detail`) never enter `FEATURES`.
- Gate: rebuild with all data from g on removed; 200/200 rows must be identical.

### 5.2 Models (Phase 4)

```
features.parquet ──► split by season ──► train 2020-21..2023-24
                                         val   2024-25   (early stopping, tuning)
                                         test  2025-26   (touched once, for the report)
                   ──► baselines: rolling-5 points x fixtures ; FPL xP
                   ──► LightGBM regressor per horizon h ∈ {1,3,5}, target y_h, objective L2 (tweedie as a variant)
                   ──► refit on train+val, score live rows
```

| Decision | Choice | Alternative | Why |
|---|---|---|---|
| Algorithm | LightGBM, one model per horizon | One model with horizon as a feature; LSTM | Tabular, small data, handles NaN (pre-2022 xG) and categoricals natively; fast |
| Rows trained on | Finished player-GWs with >= 1 fixture, positions GK/DEF/MID/FWD | Include blank GWs | Blank GW target is 0 by rule; handled at prediction time |
| Per-GW xPts for GW g+k | 1-GW model applied to the live row for GW g+k (features as of last finished GW) | Separate models per lead time | Needed for lineups/chips per GW; reuses the h=1 model |
| Confidence flag | `low` if `games_played_in_PL < 5` or `prior_weight > 0.5` or `role == unknown` | Prediction intervals (quantile LightGBM) | Simple and explainable; quantiles are stretch |
| Availability | xPts x `chance_of_playing_next_round`/100 for next GW; status `u` or `n` (left / unavailable) = 0 | Learn it | Only exists live (train/serve skew) |

Metrics per model x horizon x segment (returning / new): MAE, RMSE, Spearman, top-N hit rate by position. Feature importance chart (gain). Report: `reports/model_report.md`.

### 5.3 Recommender (Phase 5): one ILP core, five uses

One PuLP model builder, configured per use case. Solver: CBC (bundled with PuLP).

```
Variables (per player p in the pool):
  x_p  ∈ {0,1}  in squad           s_p ∈ {0,1}  starts
  c_p  ∈ {0,1}  captain            v_p ∈ {0,1}  vice
  in_p, out_p ∈ {0,1}  transfer in / out   (transfer mode only)

Objective:  max  Σ_p xpts_p · (s_p + c_p)  +  ε · Σ_p xpts_p · (x_p − s_p)  −  4 · hits
            (ε ≈ 0.1 values bench depth; xpts = chosen horizon)

Constraints:
  Σ x_p = 15;  GK 2, DEF 5, MID 5, FWD 3
  Σ x_p over each club ≤ 3
  Σ s_p = 11;  s_p ≤ x_p;  GK starters = 1; DEF ≥ 3; MID ≥ 2; FWD ≥ 1
  Σ c_p = 1;  Σ v_p = 1;  c_p + v_p ≤ 1;  c_p ≤ s_p;  v_p ≤ s_p
  Budget:  Σ price_p · x_p ≤ bank + value of current squad   (transfer mode)
           Σ price_p · x_p ≤ 100.0                            (squad build)
  Transfer mode:  x_p = current_p + in_p − out_p;  hits ≥ Σ in_p − free_transfers;  hits ≥ 0
```

| Use | How |
|---|---|
| Transfers | Transfer mode, xpts = 3 or 5 GW horizon. Solve with max transfers k = 0..FT+2 and show net gain of each, so the -4 trade-off is explicit |
| Captain + vice | Rank starters by next-GW xPts; show top 5 (no solve needed) |
| XI + bench order | Fix x to the current squad, maximise next-GW xPts; bench ordered by xPts (GK last) |
| Squad from scratch | Squad-build mode, budget 100.0, xpts = 5 GW |
| Free Hit | For each GW in the window: best unconstrained squad for that GW minus current squad's best XI. Pick the max |
| Bench Boost | For each GW: sum of the bench xPts of the current squad (after planned transfers). Pick the max; flag DGWs |

DGW/BGW detection comes from `team_schedule_ahead` (`n_fix` per team per GW), already built.

### 5.4 User team data

- `entry/{id}/event/{gw}/picks`: current 15, captain, chip used.
- `entry/{id}/` and `entry/{id}/history/`: bank and transfers made, used to estimate free transfers.
- Public API gaps: **selling price** (needs login) and the exact free-transfer count. Design: use `now_cost` as selling price and an estimated FT count, both **editable in the app**. Logged as an assumption.

### 5.5 App (Phase 6)

```
Sidebar: team ID, GW (default next), free transfers, bank, horizon (1/3/5)
Tabs:
  My Team     pitch view, XI + bench, captain, low-confidence badges
  Transfers   options for 0..FT+2 transfers with net gain after hits
  Captain     top 5 with xPts and fixture
  Squad build best 15 from scratch
  Chips       BB / FH value per GW, best GW highlighted, DGW/BGW markers
  Explorer    filter/sort all players, xPts by horizon, charts
  Model       metrics table + feature importance (from reports/)
```

- Look: custom theme (`.streamlit/config.toml`), team colours on player cards, Plotly charts. Fixes the "bland app" complaint.
- Performance: predictions loaded once with `st.cache_data`; ILP solves cached by (team, FT, bank, horizon).
- Unicode: all lookups by `player_id`; names rendered as stored (NFC UTF-8).

### 5.6 Refresh orchestration (Phase 6)

```
python refresh.py [--retrain] [--skip-ingest]
  1. ingest     historical: skip if manifest exists; live: API (cached 1 h)
  2. clean      ~5 s
  3. features   ~35 s
  4. predict    load models; retrain only with --retrain or at season rollover
  5. evals      fast gates only (skip network-heavy rerun check)
  6. write      predictions.parquet, model_report.md, refresh_log.json
```

Fail-fast: each stage raises on a broken contract; the app keeps showing the last good predictions with their timestamp.

### 5.7 Errors and retries

| Failure | Handling |
|---|---|
| Network error / 5xx | 3 retries, exponential backoff; then stale cache if present; else stop with a clear error |
| FPL API schema change | Clean/feature stages select columns explicitly, so a missing column fails loudly |
| GW in progress | Only `finished` GWs feed features and targets |
| Player with no history | Prior-filled features + `low` confidence badge |
| Infeasible ILP (e.g. bank too low) | Return "no valid move" with the binding constraint, never a partial squad |

## 6. Scale and performance

| Item | Size / time | Headroom |
|---|---|---|
| Raw data | ~66 MB | Fine on any laptop |
| `player_gw` / `features` | 8 MB / 19 MB parquet | Grows ~30k rows per season |
| Cold live ingest | ~12 min (671 player histories at 1 req/s) | Main bottleneck; see section 8 |
| Warm refresh | ~1 min | |
| LightGBM training | < 1 min per horizon (~150k rows x 86 features) | |
| ILP solve | < 1 s typical (~670 binaries) | 10 s gate |

No horizontal scaling needed: single user, batch job, in-process solver.

## 7. Monitoring and quality

- **Eval gates** per phase (`make evals`): leakage, reconciliation, constraints, metrics vs baselines.
- **Prediction log**: each refresh appends predictions to `data/processed/pred_log/<gw>.parquet`; after the GW finishes, compare with actual points. Live MAE per GW in the Model tab shows drift.
- **Refresh log**: stage timings, row counts, data hashes in `refresh_log.json`.

## 8. Trade-offs

| Decision | Chosen | Gave up | Revisit when |
|---|---|---|---|
| Storage | Parquet files | SQL queries, concurrent writers | Multiple users or ad-hoc SQL needed: DuckDB over the same parquet |
| Orchestration | Plain Python + Make | Scheduling, retries per task, UI | Scheduled refreshes: cron first, then Prefect/Dagster |
| Live ingest | Full element-summary pull | Speed (~12 min cold) | Now-ish: incremental pull via `event/{gw}/live` for new GWs only |
| Model | LightGBM per horizon | Sequence modelling | DL beats GBM on the test season (stretch) |
| Confidence | Rule-based flag | Calibrated intervals | Quantile LightGBM is cheap to add |
| Transfer planning | Single-period ILP on horizon xPts | True multi-GW plan (transfers spread over weeks, banking FTs) | Multi-period ILP with per-GW variables |
| Selling price | `now_cost` | Exact budget | Optional login-based fetch |
| History source | vaastav GitHub | Independence from a third party | vaastav stops updating: rebuild completed seasons from saved API histories |

## 9. Season rollover (once a year)

1. When 2026-27 finishes, move it to `HIST_SEASONS`. Its raw data comes from the saved API player histories, so vaastav is not required.
2. Set `LIVE_SEASON = "2027-28"`, retrain with `--retrain` (train window slides forward one season).
3. Rerun all eval gates.

## 10. Open questions

1. Transfer horizon default: 3 or 5 GWs?
2. Should the app ever log in to FPL for exact selling prices and free transfers, or stay public-only?
3. Is a scheduled weekly refresh wanted, or manual before each deadline?
