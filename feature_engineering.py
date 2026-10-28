from __future__ import annotations

import argparse
import json
from pathlib import Path

from ml_pipeline import TRAINING_FEATURES_FILE, ensure_artifacts_dir


def sanitize_cell_source(source: str) -> str:
    lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("%"):
            continue
        if ".to_csv(" in line:
            continue
        lines.append(line)
    return "\n".join(lines)


def execute_notebook(notebook_path: Path, input_file: str):
    notebook = json.loads(notebook_path.read_text())
    namespace = {"NOTEBOOK_INPUT_FILE": input_file}

    for cell in notebook.get("cells", []):
        if cell.get("cell_type") != "code":
            continue

        source = "".join(cell.get("source", []))
        source = sanitize_cell_source(source)
        if not source.strip():
            continue

        if "pd.read_excel(" in source:
            source = (
                "# Rebound notebook input path for scripted execution\n"
                "df = pd.read_excel(NOTEBOOK_INPUT_FILE)\n"
                'print(f"Loaded notebook input from {NOTEBOOK_INPUT_FILE}")\n'
                "backup_df = df.copy()\n"
            )

        exec(compile(source, f"{notebook_path.name}", "exec"), namespace)

    if "df" not in namespace:
        raise RuntimeError("Notebook execution completed but no final `df` dataframe was produced.")

    return namespace["df"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run feature engineering from fpl.ipynb and save the final dataframe.")
    parser.add_argument(
        "--input",
        default="fpl_history.xlsx",
        help="Historical Excel file consumed by the notebook.",
    )
    parser.add_argument(
        "--notebook",
        default="fpl.ipynb",
        help="Notebook to execute for feature engineering.",
    )
    parser.add_argument(
        "--output",
        default=str(TRAINING_FEATURES_FILE),
        help="Output path for engineered features.",
    )
    args = parser.parse_args()

    ensure_artifacts_dir()
    df_features = execute_notebook(Path(args.notebook), args.input)
    df_features.to_csv(args.output, index=False)
    print(f"Saved engineered features to {args.output} ({len(df_features)} rows)")


if __name__ == "__main__":
    main()
