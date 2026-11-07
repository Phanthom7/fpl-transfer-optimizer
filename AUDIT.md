# Phase 0 audit

Repo state audited: commit `81a5e8e` (before rebuild). Every tracked file listed.

| file | what it does | verdict | new location |
|---|---|---|---|
| `.gitignore` | ignore rules | keep (updated) | `.gitignore` |
| `README.md` | project readme | keep (rewritten in Phase 6) | `README.md` |
| `requirements.txt` | dependencies | keep (updated) | `requirements.txt` |
| `app.py` | one-line re-export of serve_app | archive | `archive/legacy_code/app.py` |
| `serve_app.py` | Streamlit UI, pitch view, name-based merges | adapt (pitch layout ideas for Phase 6) | `archive/legacy_code/serve_app.py` |
| `fpl_engine.py` | squad fetch, name-based prediction merge, PuLP transfers | adapt (PuLP constraints for Phase 5, ID joins) | `archive/legacy_code/fpl_engine.py` |
| `ml_pipeline.py` | paths, `normalize_name` (root cause of accent bug), live features | adapt (next-opponent map only) | `archive/legacy_code/ml_pipeline.py` |
| `feature_engineering.py` | `exec`s fpl.ipynb cells | archive | `archive/legacy_code/feature_engineering.py` |
| `train_model.py` | HistGBR + sequential feature selection | archive | `archive/legacy_code/train_model.py` |
| `generate_predictions.py` | live scoring | archive | `archive/legacy_code/generate_predictions.py` |
| `lasso_feature_analysis.py` | LassoCV feature ranking | archive | `archive/legacy_code/lasso_feature_analysis.py` |
| `fill_data_v2.py` | median imputation, hardcoded local path | archive | `archive/legacy_code/fill_data_v2.py` |
| `team2026.py` | scratch: fetch one team's picks | archive | `archive/legacy_code/team2026.py` |
| `fpl.ipynb` | feature engineering notebook | archive | `archive/notebooks/fpl.ipynb` |
| `df.ipynb` | data peek notebook | archive | `archive/notebooks/df.ipynb` |
| `docs/README.original.md` | original readme | archive | `archive/README.original.md` |
| `cleaned_merged_seasons.csv` | GW data 2016-18, 2020-24 | archive | `archive/legacy_data/cleaned_merged_seasons.csv` |
| `fpl_cleaned_ml.csv` | imputed training table 2020-24 | archive | `archive/legacy_data/fpl_cleaned_ml.csv` |
| `fpl_test.csv` | older training table variant | archive | `archive/legacy_data/fpl_test.csv` |
| `fpl_2024:25.csv` | 2024-25 season totals | archive | `archive/legacy_data/fpl_2024:25.csv` |
| `fpl_predictions_v2.csv` | old predictions | archive | `archive/legacy_data/fpl_predictions_v2.csv` |
| `fpl_predictions_v3.csv` | old predictions | archive | `archive/legacy_data/fpl_predictions_v3.csv` |
