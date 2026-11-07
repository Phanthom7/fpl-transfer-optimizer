"""Print an inventory of data/raw."""
from __future__ import annotations

import json

import pandas as pd

from src.config import ALL_SEASONS, RAW_DIR


def inventory() -> pd.DataFrame:
    rows = []
    for s in ALL_SEASONS:
        m = RAW_DIR / "vaastav" / s / "_manifest.json"
        if not m.exists():
            continue
        files = json.loads(m.read_text())["files"]
        gw = pd.read_parquet(RAW_DIR / "vaastav" / s / "merged_gw.parquet", columns=["GW"])
        xg = "expected_goals" in pd.read_parquet(RAW_DIR / "vaastav" / s / "merged_gw.parquet").columns
        rows.append({"season": s, "gw_rows": files["merged_gw"]["rows"], "players": files["players_raw"]["rows"],
                     "gw_range": f"{int(gw.GW.min())}-{int(gw.GW.max())}", "xg_per_gw": xg,
                     "understat": "understat_player" in files})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print(inventory().to_markdown(index=False))
