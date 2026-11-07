from __future__ import annotations

import argparse
import math

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.feature_selection import SequentialFeatureSelector
from sklearn.metrics import mean_squared_error

from ml_pipeline import FEATURE_COLUMNS, TRAINING_FEATURES_FILE, save_model_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the FPL points model.")
    parser.add_argument(
        "--input",
        default=str(TRAINING_FEATURES_FILE),
        help="Engineered features CSV from feature_engineering.py.",
    )
    args = parser.parse_args()

    df_train = pd.read_csv(args.input).fillna(0)

    train_mask = df_train["season_x"] < "2023-24"
    val_mask = df_train["season_x"] == "2023-24"

    if not train_mask.any():
        raise ValueError("No training rows found before season 2023-24.")
    if not val_mask.any():
        raise ValueError("No validation rows found for season 2023-24.")

    X_train = df_train.loc[train_mask, FEATURE_COLUMNS]
    y_train = df_train.loc[train_mask, "total_points"]
    X_val = df_train.loc[val_mask, FEATURE_COLUMNS]
    y_val = df_train.loc[val_mask, "total_points"]

    selection_model = HistGradientBoostingRegressor(
        max_iter=50,
        learning_rate=0.1,
        max_depth=5,
        random_state=42,
    )

    sfs_forward = SequentialFeatureSelector(
        selection_model,
        n_features_to_select="auto",
        direction="forward",
        scoring="neg_mean_squared_error",
        cv=3,
        n_jobs=-1,
    )
    sfs_forward.fit(X_train, y_train)
    forward_features = list(np.array(FEATURE_COLUMNS)[sfs_forward.get_support()])

    sfs_backward = SequentialFeatureSelector(
        selection_model,
        n_features_to_select="auto",
        direction="backward",
        scoring="neg_mean_squared_error",
        cv=3,
        n_jobs=-1,
    )
    sfs_backward.fit(X_train, y_train)
    backward_features = list(np.array(FEATURE_COLUMNS)[sfs_backward.get_support()])

    selected_features = sorted(set(forward_features).union(set(backward_features)))

    model = HistGradientBoostingRegressor(
        max_iter=200,
        learning_rate=0.05,
        max_depth=7,
        l2_regularization=0.1,
        random_state=42,
    )
    model.fit(X_train[selected_features], y_train)

    val_predictions = model.predict(X_val[selected_features])
    rmse = math.sqrt(mean_squared_error(y_val, val_predictions))

    metadata = {
        "selected_features": selected_features,
        "validation_rmse": rmse,
        "training_rows": int(train_mask.sum()),
        "validation_rows": int(val_mask.sum()),
        "train_seasons_before": "2023-24",
        "validation_season": "2023-24",
    }
    save_model_artifacts(model, metadata)

    print(f"Selected {len(selected_features)} features")
    print(f"Validation RMSE: {rmse:.4f}")


if __name__ == "__main__":
    main()
