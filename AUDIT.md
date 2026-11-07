# Phase 0 audit

Repo state audited: commit `81a5e8e` (before rebuild). Every tracked file listed.

| file | what it does | verdict | now |
|---|---|---|---|
| `.gitignore` | ignore rules | keep (updated) | `.gitignore` |
| `README.md` | project readme | keep (rewritten in Phase 6) | `README.md` |
| `requirements.txt` | dependencies | keep (updated) | `requirements.txt` |
| `app.py` | one-line re-export of serve_app | archive | deleted (recoverable: git 81a5e8e) |
| `serve_app.py` | Streamlit UI, pitch view, name-based merges | adapt (pitch layout ideas for Phase 6) | deleted (recoverable: git 81a5e8e) |
| `fpl_engine.py` | squad fetch, name-based prediction merge, PuLP transfers | adapt (PuLP constraints for Phase 5, ID joins) | deleted (recoverable: git 81a5e8e) |
| `ml_pipeline.py` | paths, `normalize_name` (root cause of accent bug), live features | adapt (next-opponent map only) | deleted (recoverable: git 81a5e8e) |
| `feature_engineering.py` | `exec`s fpl.ipynb cells | archive | deleted (recoverable: git 81a5e8e) |
| `train_model.py` | HistGBR + sequential feature selection | archive | deleted (recoverable: git 81a5e8e) |
| `generate_predictions.py` | live scoring | archive | deleted (recoverable: git 81a5e8e) |
| `lasso_feature_analysis.py` | LassoCV feature ranking | archive | deleted (recoverable: git 81a5e8e) |
| `fill_data_v2.py` | median imputation, hardcoded local path | archive | deleted (recoverable: git 81a5e8e) |
| `team2026.py` | scratch: fetch one team's picks | archive | deleted (recoverable: git 81a5e8e) |
| `fpl.ipynb` | feature engineering notebook | archive | deleted (recoverable: git 81a5e8e) |
| `df.ipynb` | data peek notebook | archive | deleted (recoverable: git 81a5e8e) |
| `docs/README.original.md` | original readme | archive | deleted (recoverable: git 81a5e8e) |
| `cleaned_merged_seasons.csv` | GW data 2016-18, 2020-24 | archive | deleted (recoverable: git 81a5e8e) |
| `fpl_cleaned_ml.csv` | imputed training table 2020-24 | archive | deleted (recoverable: git 81a5e8e) |
| `fpl_test.csv` | older training table variant | archive | deleted (recoverable: git 81a5e8e) |
| `fpl_2024:25.csv` | 2024-25 season totals | archive | deleted (recoverable: git 81a5e8e) |
| `fpl_predictions_v2.csv` | old predictions | archive | deleted (recoverable: git 81a5e8e) |
| `fpl_predictions_v3.csv` | old predictions | archive | deleted (recoverable: git 81a5e8e) |
