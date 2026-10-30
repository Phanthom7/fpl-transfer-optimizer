# FPL Transfer Optimizer

Fantasy Premier League helper: trains a points model on historical seasons, predicts upcoming points from the live FPL API, and recommends transfers through a Streamlit app.

Original README (more pipeline detail) is preserved at `docs/README.original.md`.

## Stack

| Layer | Tools |
|---|---|
| Language | Python |
| Data | pandas, numpy, openpyxl |
| Model | scikit-learn `HistGradientBoostingRegressor` with `SequentialFeatureSelector` (`train_model.py`); `LassoCV` for feature inspection (`lasso_feature_analysis.py`) |
| Optimizer | PuLP linear programming (`fpl_engine.optimize_transfers`) |
| App | Streamlit (`serve_app.py`; `app.py` just re-exports it) |
| Live data | Public FPL API (`bootstrap-static`, `fixtures`, `entry/{id}/event/{gw}/picks`) |

## Pipeline

```
fpl.ipynb (feature logic) -> feature_engineering.py -> artifacts/training_features.csv
                                lasso_feature_analysis.py (optional, inspection only)
artifacts/training_features.csv -> train_model.py -> artifacts/model.pkl + model_metadata.json
live FPL API + model -> generate_predictions.py -> artifacts/predictions.csv
artifacts/predictions.csv -> serve_app.py (Streamlit)
```

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python feature_engineering.py --input /path/to/fpl_history.xlsx
python train_model.py
python generate_predictions.py
streamlit run serve_app.py
```

## Files

| Path | What it is |
|---|---|
| `feature_engineering.py`, `train_model.py`, `generate_predictions.py`, `serve_app.py` | The 4 pipeline stages |
| `ml_pipeline.py` | Shared paths (`artifacts/`), feature helpers, model save/load |
| `fpl_engine.py` | Squad fetch, prediction merge, transfer optimization (490 lines) |
| `lasso_feature_analysis.py` | LassoCV coefficient ranking |
| `team2026.py` | Scratch script: fetches one team's picks for a hardcoded entry id and gameweek |
| `fpl.ipynb`, `df.ipynb` | Notebooks; `fpl.ipynb` is the feature-engineering source of truth per the original README |
| `*.csv` | Historical and prediction data (~53 MB total) |

## Notes

- `artifacts/` is gitignored. Run the pipeline once before launching the app.
