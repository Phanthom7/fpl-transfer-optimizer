# PLAN

Goal: expected points (xPts) model + Streamlit recommender (transfers, captain, XI, squad build, chips).
Budget: 2 days x 6+ hrs. Checkpoint after every phase.

## Architecture

```
vaastav GitHub CSVs (2018-19 .. 2025-26) ─┐
FPL API (live 2026-27) ───────────────────┼─> data/raw/*.parquet   (src/ingest)
                                          │
                                          v
                 data/interim/player_gw.parquet       (src/clean)  keyed on player `code`, never name
                                          v
                 data/processed/features.parquet      (src/features) strictly lagged
                                          v
                 models/*.pkl + predictions.parquet   (src/models)  1/3/5 GW horizons
                                          v
                 PuLP ILP                              (src/recommender)
                                          v
                 Streamlit app                         (app/)
refresh.py runs the whole chain.
```

## Phases

| # | Phase | Must hrs | Stretch hrs | Must-have | Stretch |
|---|---|---|---|---|---|
| 0 | Audit + plan | 0.5 | 0 | audit, PLAN, DECISIONS, AUDIT | |
| 1 | Ingest | 1.5 | 0.5 | 7 seasons hist + live 2026/27, parquet, cache, idempotent | xG scraping (Understat/FBref) |
| E | Eval gates | 1.0 | 0 | eval suite, scorecards, retro-evals P0/P1, P2 draft | |
| 2 | Clean | 2.0 | 0 | one player-GW table, cross-season ID map, DGW/BGW, 2019/20 GW fix, status flags, DQ report | |
| 3 | Features | 2.0 | 1.0 | rolling 3/5/10, fixture/FDR, team form, minutes risk, cold-start priors, games_played_in_PL | high-scoring fixture flag, prior-league stats scaled by league factor |
| 4 | Model | 1.5 | 2.0 | baselines (rolling avg, FPL xP), LightGBM 1/3/5 GW, metrics by segment, importance chart, live scoring | LSTM/transformer (ship only if beats GBM) |
| 5 | Recommender | 1.75 | 1.0 | ILP squad build, transfers w/ hits, captain top 5, XI + bench, BB/FH timing | backtest vs baseline on test season |
| 6 | App + refresh | 1.75 | 0.5 | styled Streamlit, tabs, team ID input, `make refresh`, README | chart polish, theme toggle |
| | **Total** | **12.0** | **5.0** | | |

Budget: 2 days x 6 h = 12 h floor. Must-have fits exactly; stretch only from time beyond 12 h or time saved.

## Day schedule (working app guaranteed by end of Day 2)

| Block | Work |
|---|---|
| Day 1 AM | P0, P1, eval gates |
| Day 1 PM | P2, P3 (core features first, cold start second) |
| Day 2 AM | P4: 1 GW LightGBM first, then 3/5 GW. Score live. |
| Day 2 midday | P5: squad build + transfers + captain/XI (must), chips next |
| Day 2 PM | P6: app wired to saved predictions. Then stretch in priority order. |

Fallback rule: if behind at Day 2 midday, ship app on 1 GW + 3 GW only, chips via 3 GW projections, drop backtest and all stretch.

Stretch priority (first cut last): 1. recommender backtest, 2. high-scoring fixture flag, 3. prior-league stats, 4. xG scraping, 5. deep learning.

## Fixes for old pain points

| Old problem | Fix |
|---|---|
| Players with accents/special chars dropped or mismatched | All joins on numeric IDs (`element` within season, `code` across seasons). Names are display only, stored as UTF-8 NFC. Test with names like Ødegaard, Mitrović, Gyökeres. |
| Bland app | Custom theme (`.streamlit/config.toml`), pitch view, player cards with team colours, Plotly charts, badges for low confidence/DGW. |
| Notebook exec as pipeline (`exec` of fpl.ipynb) | Plain modules + pytest. |
| Validation leakage risk (same-GW stats as features) | All features shifted by >= 1 GW; leakage test. |

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| `fantasy.premierleague.com` blocked by sandbox proxy (confirmed 403) | No live API here | Use vaastav 2026-27 mirror (confirmed reachable). API client still built + tested with fixtures; runs on your machine. Or allow host in env settings. |
| Understat/FBref blocked (confirmed 403) + ToS limits | No scraped xG | Use FPL-native `expected_goals`/`expected_assists` (in vaastav from 2022-23). Older seasons: NaN + missing flag. Scraping = stretch. |
| xG only from 2022-23 | Fewer seasons with xG | GBM handles NaN natively; add `has_xg` flag. |
| Scoring rule changes (2025-26 defensive contribution points) | Target shift | Season as feature; test on most recent full season (2025-26). |
| 2019/20 GW 39-47 numbering (COVID restart) | Broken rolling windows | Remap to 30-38 in clean. |
| Prior-league data for new signings unavailable | Weaker cold start | Priors from position x price bracket x team strength. |
| Time | Lose stretch | Cut order above. |
