# Phase 0 scorecard

Gate: **BLOCKED**  
Run: 2026-11-08T00:00:38.741121+00:00

| check | tier | value | threshold | status | note |
|---|---|---|---|---|---|
| Audit table covers 100% of repo files | CRITICAL | 22/22 | 100% | PASS |  |
| Zero deletions vs pre-rebuild repo (archive moves only) | CRITICAL | deleted=19 lost_blobs=19 | 0 | FAIL | ['D\tapp.py', 'D\tcleaned_merged_seasons.csv', 'D\tdf.ipynb', 'D\tdocs/README.original.md', 'D\tfeature_engineering.py', 'D\tfill_data_v2.py', 'D\tfpl.ipynb', 'D\tfpl_2024:25.csv', 'D\tfpl_cleaned_ml.csv', 'D\tfpl_engine.py', 'D\tfpl_predictions_v2.csv', 'D\tfpl_predictions_v3.csv', 'D\tfpl_test.csv', 'D\tgenerate_predictions.py', 'D\tlasso_feature_analysis.py', 'D\tml_pipeline.py', 'D\tserve_app.py', 'D\tteam2026.py', 'D\ttrain_model.py'] ['fpl_predictions_v3.csv', 'ml_pipeline.py', 'team2026.py', 'app.py', 'lasso_feature_analysis.py', 'fpl_cleaned_ml.csv', 'cleaned_merged_seasons.csv', 'df.ipynb', 'train_model.py', 'docs/README.original.md', 'fpl_predictions_v2.csv', 'fpl_2024:25.csv', 'fpl_engine.py', 'feature_engineering.py', 'fpl.ipynb', 'serve_app.py', 'generate_predictions.py', 'fpl_test.csv', 'fill_data_v2.py'] |
| PLAN.md must-have hours fit 2-day budget | PASS | 12.0 h (Must hrs) | <= 12.0 h | PASS |  |
| Must-have vs stretch clearly split | GOOD | cols=True every_phase_has_must=True priority_list=True | all true | PASS |  |
