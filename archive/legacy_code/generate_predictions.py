from __future__ import annotations

import argparse

from ml_pipeline import PREDICTIONS_FILE, build_live_features, ensure_artifacts_dir, fetch_fixtures, fetch_live_data, load_model_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate live FPL predictions from the trained model.")
    parser.add_argument(
        "--output",
        default=str(PREDICTIONS_FILE),
        help="Where to write the predictions CSV.",
    )
    args = parser.parse_args()

    model, metadata = load_model_artifacts()
    selected_features = metadata["selected_features"]

    elements, teams, current_gw = fetch_live_data()
    fixtures = fetch_fixtures()
    df_live = build_live_features(elements, teams, fixtures, current_gw)
    df_live["predicted_points"] = model.predict(df_live[selected_features].fillna(0))

    output_columns = [
        "name",
        "predicted_points",
        "value",
        "position",
        "team",
        "id",
        "now_cost",
        "element_type",
        "status",
        "chance_of_playing_next_round",
        "team_short_name",
        "full_name",
    ]
    ensure_artifacts_dir()
    df_live[output_columns].sort_values("predicted_points", ascending=False).to_csv(args.output, index=False)
    print(f"Saved live predictions to {args.output} ({len(df_live)} players)")


if __name__ == "__main__":
    main()
