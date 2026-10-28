# AGENTS.md: FPL Transfer Optimizer

Rules for AI coding agents working in this folder.

## Context
- Read `README.md` and `PROJECT.md` first. `fpl.ipynb` is the feature-engineering source of truth; `feature_engineering.py` executes it.
- All generated files go to `artifacts/` (gitignored). Never write outputs to the project root.

## Commands
- Setup: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Pipeline: `feature_engineering.py --input <xlsx>` -> `train_model.py` -> `generate_predictions.py` -> `streamlit run serve_app.py`

## Rules
- Keep the train/validation split as is: seasons before 2023-24 train, 2023-24 validates. Ask before changing it.
- The live FPL API is public and unauthenticated. Do not add API keys.
- Do not edit the large CSVs in place. Write new files instead.
- Prefer small, reviewable changes; the owner reviews diffs on a phone.
- No em dashes in docs or copy.
