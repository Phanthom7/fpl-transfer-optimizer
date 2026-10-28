from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LassoCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml_pipeline import ARTIFACTS_DIR, TRAINING_FEATURES_FILE, ensure_artifacts_dir

TARGET_COLUMN = "total_points"

EXCLUDED_COLUMNS = {
    TARGET_COLUMN,
    "name",
    "season_x",
    "GW",
    "team_h_score",
    "team_a_score",
    "fixture",
}


def build_feature_matrix(df: pd.DataFrame):
    feature_df = df.drop(columns=[col for col in EXCLUDED_COLUMNS if col in df.columns]).copy()

    numeric_columns = feature_df.select_dtypes(include=["number", "bool"]).columns.tolist()
    categorical_columns = [
        col for col in feature_df.columns if col not in numeric_columns
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_columns,
            ),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                categorical_columns,
            ),
        ]
    )

    X = preprocessor.fit_transform(feature_df)
    feature_names = preprocessor.get_feature_names_out()
    return X, feature_names, feature_df.columns.tolist()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run LassoCV on notebook-engineered features to identify important model inputs."
    )
    parser.add_argument(
        "--input",
        default=str(TRAINING_FEATURES_FILE),
        help="Engineered feature CSV produced by feature_engineering.py.",
    )
    parser.add_argument(
        "--target",
        default=TARGET_COLUMN,
        help="Regression target column.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=25,
        help="Number of top absolute-coefficient features to print.",
    )
    parser.add_argument(
        "--alpha-count",
        type=int,
        default=100,
        help="Number of alpha values for LassoCV.",
    )
    args = parser.parse_args()

    ensure_artifacts_dir()
    df = pd.read_csv(args.input)
    if args.target not in df.columns:
        raise ValueError(f"Target column `{args.target}` not found in {args.input}")

    y = df[args.target].fillna(0)
    X, transformed_feature_names, raw_feature_names = build_feature_matrix(df)

    model = LassoCV(cv=5, random_state=42, n_alphas=args.alpha_count, max_iter=20000)
    model.fit(X, y)

    coefficients = pd.DataFrame(
        {
            "feature": transformed_feature_names,
            "coefficient": model.coef_,
        }
    )
    coefficients["abs_coefficient"] = coefficients["coefficient"].abs()
    coefficients = coefficients.sort_values("abs_coefficient", ascending=False)

    selected = coefficients[coefficients["abs_coefficient"] > 0].copy()
    selected["raw_feature"] = selected["feature"].str.replace(
        r"^(numeric|categorical)__", "", regex=True
    )
    recommended_raw_features = sorted(selected["raw_feature"].unique().tolist())

    coefficients_output = ARTIFACTS_DIR / "lasso_feature_importance.csv"
    selected_output = ARTIFACTS_DIR / "lasso_selected_features.json"
    summary_output = ARTIFACTS_DIR / "lasso_summary.json"

    coefficients.to_csv(coefficients_output, index=False)
    selected_output.write_text(json.dumps(recommended_raw_features, indent=2))
    summary_output.write_text(
        json.dumps(
            {
                "input_file": str(args.input),
                "target": args.target,
                "alpha": model.alpha_,
                "selected_feature_count": len(recommended_raw_features),
                "selected_features": recommended_raw_features,
                "candidate_raw_feature_count": len(raw_feature_names),
            },
            indent=2,
        )
    )

    print(f"Lasso alpha: {model.alpha_:.6f}")
    print(f"Selected {len(recommended_raw_features)} raw features")
    print("Top features:")
    for _, row in coefficients.head(args.top_k).iterrows():
        print(f"  {row['feature']}: {row['coefficient']:.4f}")
    print(f"Saved coefficient rankings to {coefficients_output}")
    print(f"Saved selected feature list to {selected_output}")
    print(f"Saved summary to {summary_output}")


if __name__ == "__main__":
    main()
