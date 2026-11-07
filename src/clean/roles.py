"""Playing role, club tenure and detailed status.

Leak-free columns (use only matches BEFORE the row): role, starts_last5, apps_last5,
gws_at_club, apps_at_club, days_at_club.
Descriptive columns (use the row or whole season, NOT model features): appearance, role_season, status_detail.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ROLE_WINDOW = 5
STARTER_SHARE = 0.6   # started >= 60% of window
SUB_SHARE = 0.4       # appeared >= 40% of window
SEASON_STARTER_SHARE = 0.5  # season role: absences from injury/bans are not visible, so looser
SEASON_SUB_SHARE = 0.25
STARTER_MIN_PROXY = 60  # 60+ min = started (FPL's own appearance threshold)
SIGNING_PRICE = {"GK": 4.5, "DEF": 4.5, "MID": 5.0, "FWD": 5.0}


def started(df: pd.DataFrame) -> pd.Series:
    # `starts` missing before 2022-23 and only partly filled in 2022-23; 60+ min also counts as a start
    return ((df["starts"].fillna(0) >= 1) | (df["minutes"] >= STARTER_MIN_PROXY)).to_numpy()


def appearance(df: pd.DataFrame) -> pd.Series:
    st = started(df)
    return pd.Series(np.select([st, df["minutes"] > 0], ["started", "sub_on"], "unused"), index=df.index)


def classify_role(starts_share, apps_share, n, starter=STARTER_SHARE, sub=SUB_SHARE) -> np.ndarray:
    return np.select(
        [n == 0, starts_share >= starter, apps_share >= sub],
        ["unknown", "starter", "substitute"], "benchwarmer")


def add_roles(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["appearance"] = appearance(df)
    real = ~df["is_ghost_fixture"].astype(bool)
    d = df[real].sort_values(["player_id", "kickoff_time", "fixture"])
    g = d.groupby("player_id", sort=False)
    st = (d["appearance"] == "started").astype(int)
    ap = (d["minutes"] > 0).astype(int)
    # rolling over the player's previous ROLE_WINDOW matches (all clubs/seasons), excluding current
    roll = lambda s: s.groupby(d["player_id"]).transform(lambda x: x.shift(1).rolling(ROLE_WINDOW, min_periods=1).sum())
    n_prev = g.cumcount().clip(upper=ROLE_WINDOW)
    s5, a5 = roll(st).fillna(0), roll(ap).fillna(0)
    with np.errstate(divide="ignore", invalid="ignore"):
        d["starts_last5"], d["apps_last5"] = s5.astype(int), a5.astype(int)
        d["role"] = classify_role(s5 / n_prev, a5 / n_prev, n_prev)

    # tenure: contiguous spells at one club (spell continues across seasons and gap seasons)
    spell = (d["team_code"] != g["team_code"].shift()).astype(int).groupby(d["player_id"]).cumsum()
    key = [d["player_id"], spell]
    d["gws_at_club"] = d.groupby(key).cumcount()
    d["apps_at_club"] = ap.groupby(key).transform(lambda x: x.shift(1, fill_value=0).cumsum())
    t = pd.to_datetime(d["kickoff_time"], utc=True)
    d["days_at_club"] = (t - t.groupby(key).transform("min")).dt.days

    cols = ["starts_last5", "apps_last5", "role", "gws_at_club", "apps_at_club", "days_at_club"]
    df = df.join(d[cols])
    for c in cols[:2] + cols[3:]:  # counts stay integer (nullable: ghost rows have none)
        df[c] = df[c].astype("Int64")
    # ghost rows: no role info
    df.loc[~real, "role"] = "unknown"

    # season role (descriptive, whole season)
    sr = df[real].assign(_st=lambda x: x["appearance"] == "started", _ap=lambda x: x["minutes"] > 0) \
        .groupby(["player_id", "season"]).agg(n=("_st", "size"), s=("_st", "sum"), a=("_ap", "sum"))
    sr["role_season"] = classify_role(sr["s"] / sr["n"], sr["a"] / sr["n"], sr["n"], SEASON_STARTER_SHARE, SEASON_SUB_SHARE)
    return df.merge(sr["role_season"].reset_index(), on=["player_id", "season"], how="left")


def add_tenure_censoring(df: pd.DataFrame, first_season: str, prior_registered: dict[int, int]) -> pd.DataFrame:
    """club_tenure_censored: spell began at the first data season and player was at same club the season before."""
    df = df.copy()
    real = ~df["is_ghost_fixture"].astype(bool)
    d = df[real].sort_values(["player_id", "kickoff_time"])
    first = d.groupby("player_id").head(1)
    censored_ids = {p for p, s, tc in first[["player_id", "season", "team_code"]].itertuples(index=False)
                    if s == first_season and prior_registered.get(p) == tc}
    spell_start = d.groupby("player_id")["team_code"].transform(lambda x: (x != x.shift()).cumsum()) == 1
    cens = d["player_id"].isin(censored_ids) & spell_start
    df["club_tenure_censored"] = False
    df.loc[cens[cens].index, "club_tenure_censored"] = True
    return df


def add_status_detail(df: pd.DataFrame, seasons_seen_before: dict[tuple[int, str], bool]) -> pd.DataFrame:
    """Split player_status into: returning, moved_pl_club, returned_to_pl, new_promoted_club, new_signing, new_fringe."""
    df = df.copy()
    real = df[~df["is_ghost_fixture"].astype(bool)].sort_values("kickoff_time")
    first = real.groupby(["player_id", "season"]).agg(
        status=("player_status", "first"), promoted=("promoted_team", "first"),
        pos=("position", "first"), price=("price", "first")).reset_index()
    detail = []
    for p, s, st, pr, pos, price in first.itertuples(index=False):
        if st != "new_to_pl":
            detail.append(st)
        elif seasons_seen_before.get((p, s)):
            detail.append("returned_to_pl")
        elif pr:
            detail.append("new_promoted_club")
        elif price >= SIGNING_PRICE.get(pos, 99):
            detail.append("new_signing")
        else:
            detail.append("new_fringe")
    first["status_detail"] = detail
    return df.merge(first[["player_id", "season", "status_detail"]], on=["player_id", "season"], how="left")
