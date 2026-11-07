"""Data quality report for the player-GW table."""
from __future__ import annotations

import json

import pandas as pd

KEY = ["player_id", "season", "gw", "fixture"]


def report(df: pd.DataFrame) -> dict:
    real = df[~df["is_ghost_fixture"]]
    ps = real.drop_duplicates(["player_id", "season"])
    per = real.groupby("season").agg(rows=("player_id", "size"), players=("player_id", "nunique"),
                                     gws=("gw", "nunique"), dgw_rows=("is_dgw", "sum"),
                                     minutes_gt0=("minutes", lambda m: int((m > 0).sum())))
    status = ps.pivot_table(index="season", columns="status_detail", values="player_id", aggfunc="count", fill_value=0)
    role_s = ps.pivot_table(index="season", columns="role_season", values="player_id", aggfunc="count", fill_value=0).add_prefix("season_")
    flags = ps.groupby("season")[["mid_season_move", "position_changed"]].sum()
    promoted = real.drop_duplicates(["season", "team"]).groupby("season")["promoted_team"].sum().rename("promoted_teams")
    table = per.join(status).join(role_s).join(flags).join(promoted).reset_index()
    nulls = df.isna().sum()
    return {
        "rows": len(df),
        "ghost_rows": int(df["is_ghost_fixture"].sum()),
        "duplicate_keys": int(df.duplicated(KEY).sum()),
        "positions": df["position"].value_counts().to_dict(),
        "nulls": {k: int(v) for k, v in nulls[nulls > 0].items()},
        "per_season": table.to_dict(orient="records"),
    }


def to_markdown(r: dict) -> str:
    t = pd.DataFrame(r["per_season"])
    lines = ["# Data quality report: player_gw", "",
             f"- rows: {r['rows']:,}", f"- ghost rows (postponed placeholders, kept + flagged): {r['ghost_rows']}",
             f"- duplicate (player, season, gw, fixture) keys: {r['duplicate_keys']}",
             f"- positions: {r['positions']}", f"- columns with nulls: {r['nulls']}", "",
             "## Per season (ghost rows excluded)", "", t.to_markdown(index=False)]
    return "\n".join(lines) + "\n"


def write(df: pd.DataFrame, out_dir) -> dict:
    r = report(df)
    (out_dir / "dq_report.json").write_text(json.dumps(r, indent=2, default=str))
    (out_dir / "dq_report.md").write_text(to_markdown(r))
    return r
