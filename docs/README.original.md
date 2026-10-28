# FPL Transfer Optimizer

Small Python project for Fantasy Premier League squad optimization. The repo is now split into four explicit stages:

1. `feature_engineering.py`
2. `train_model.py`
3. `generate_predictions.py`
4. `serve_app.py`

## Project Layout

- `feature_engineering.py`: executes [fpl.ipynb](/Users/Vishnu/Desktop/Project/FPL/fpl.ipynb) as the canonical feature-engineering stage and writes the final dataframe to `artifacts/training_features.csv`
- `lasso_feature_analysis.py`: runs `LassoCV` on the notebook-engineered dataset and saves coefficient rankings plus a recommended feature list
- `train_model.py`: trains the model, runs feature selection, evaluates on the 2023-24 holdout split, and saves the trained model plus metadata
- `generate_predictions.py`: fetches live FPL API data and writes player predictions to `artifacts/predictions.csv`
- `serve_app.py`: Streamlit app for transfer analysis and squad recommendations
- `fpl_engine.py`: live squad fetching, predictions merge, and transfer optimization logic
- `ml_pipeline.py`: shared ML paths, feature-building helpers, and model artifact utilities

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run The Pipeline

```bash
python feature_engineering.py --input /path/to/fpl_history.xlsx
python lasso_feature_analysis.py
python train_model.py
python generate_predictions.py
streamlit run serve_app.py
```

## Feature Engineering Notebook

`fpl.ipynb` is now treated as the source of truth for historical feature engineering.

- The script runner executes the notebook cells in order.
- Notebook magics and in-notebook CSV saves are skipped during scripted runs.
- The notebook's hardcoded Excel load is rebound to the `--input` path you pass to `feature_engineering.py`.
- The final `df` dataframe produced by the notebook is what gets written to `artifacts/training_features.csv`.

## Artifacts

Generated files are written to `artifacts/`:

- `training_features.csv`
- `lasso_feature_importance.csv`
- `lasso_selected_features.json`
- `lasso_summary.json`
- `model.pkl`
- `model_metadata.json`
- `predictions.csv`

## Notes

- The app expects `artifacts/predictions.csv` to exist.
- The training split uses seasons before `2023-24` for training and `2023-24` as validation.
- Live predictions come from the official FPL API, not from the older static season CSVs.
- The notebook currently expects a historical Excel export as input, so `openpyxl` is included in the dependencies.
- The Lasso script is for feature inspection and recommendation. It does not automatically rewrite the training feature set.
