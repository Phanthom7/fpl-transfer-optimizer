# PROJECT: FPL Transfer Optimizer

| Field | Value |
|---|---|
| Status | Working code, dormant (inferred from file dates) |
| Original path | `~/workspace/side-projects/FPL` |
| Last activity | 2026-04-06 (`train_model.py`); folder touched 2026-04-17 |
| Git | **None.** A `.gitignore` exists but there is no `.git` folder, so there is no history |
| Uncommitted changes | N/A (not a repo) |

## Known issues

- No `artifacts/` folder, so `serve_app.py` has no `predictions.csv` to load until the pipeline runs.
- `feature_engineering.py` needs a historical Excel export via `--input`. No `.xlsx` file is in the project, so the source data location is unknown.
- `docs/README.original.md` links to `/Users/Vishnu/Desktop/Project/FPL/fpl.ipynb`, an old path.
- `team2026.py` hardcodes a team entry id and gameweek 24.
- Related stray file: `~/workspace/portfolio/fill_data_v2.py` is FPL data-cleaning code that reads `/Users/Vishnu/Desktop/Python/AI/FPL/fpl_cleaned.csv` (old path). It was left in the portfolio copy, not moved.

## Next steps (suggested, not decided)

1. `git init` and make a first commit so the work has history.
2. Find or re-export the historical Excel file, then run the pipeline once to produce `artifacts/`.
3. Decide whether the root CSVs are inputs or old outputs (`fpl_predictions_v2/v3.csv` look like older outputs, inferred).
4. Remove the empty `Chess/` and `Job Scraper/` folders.
