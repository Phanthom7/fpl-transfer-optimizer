"""Build data/interim/player_gw.parquet: one row per (player_id, season, gw, fixture).

player_id = FPL `code` (stable across seasons). Names are display-only.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.config import AUX_SEASONS, HIST_SEASONS, INTERIM_DIR, LIVE_SEASON, RAW_DIR

log = logging.getLogger(__name__)
VAASTAV = RAW_DIR / "vaastav"
API = RAW_DIR / "fpl_api"
POS_MAP = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD", 5: "AM"}
POS_FIX = {"GKP": "GK"}
STATS = [
    "total_points", "minutes", "starts", "goals_scored", "assists", "clean_sheets", "goals_conceded", "own_goals",
    "penalties_saved", "penalties_missed", "yellow_cards", "red_cards", "saves", "bonus", "bps",
    "influence", "creativity", "threat", "ict_index", "expected_goals", "expected_assists",
    "expected_goal_involvements", "expected_goals_conceded", "defensive_contribution",
    "clearances_blocks_interceptions", "recoveries", "tackles", "xP",
    "value", "selected", "transfers_in", "transfers_out", "transfers_balance", "team_h_score", "team_a_score",
]
OUT_COLS = [
    "season", "gw", "player_id", "code", "element", "fixture", "kickoff_time", "was_home",
    "team", "team_code", "opponent_team", "opponent_code", "position",
    "first_name", "second_name", "web_name", "price", *STATS,
    "is_ghost_fixture", "n_team_fixtures_gw", "is_dgw",
    "player_status", "promoted_team", "mid_season_move", "position_changed",
]


def latest_api_dir():
    return sorted(p for p in API.glob("*") if p.is_dir())[-1]


def _num(df: pd.DataFrame, cols) -> pd.DataFrame:
    for c in cols:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _bool(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin(["true", "1"])


def attach_team(rows: pd.DataFrame, fixtures: pd.DataFrame) -> pd.DataFrame:
    """Team per row from the fixture + was_home. Handles mid-season moves exactly."""
    fx = fixtures[["fixture", "team_h", "team_a", "fixture_gw"]]
    out = rows.merge(fx, on="fixture", how="left", validate="many_to_one")
    home = _bool(out["was_home"])
    out["team_id"] = np.where(home, out["team_h"], out["team_a"])
    out["opp_id"] = np.where(home, out["team_a"], out["team_h"])
    if "opponent_team" in out:
        bad = (pd.to_numeric(out["opponent_team"]) != out["opp_id"]).sum()
        if bad:
            raise ValueError(f"{bad} rows: opponent_team disagrees with fixture")
    out["was_home"] = home
    out["is_ghost_fixture"] = out["gw"] != out["fixture_gw"]
    return out.drop(columns=["team_h", "team_a", "opponent_team"], errors="ignore")


def load_hist(season: str) -> pd.DataFrame:
    d = VAASTAV / season
    g = pd.read_parquet(d / "merged_gw.parquet")
    n0 = len(g)
    g = g.drop_duplicates()
    log.info("%s: dropped %d exact duplicate rows", season, n0 - len(g))
    fx = pd.read_parquet(d / "fixtures.parquet").rename(columns={"id": "fixture", "gw": "fixture_gw"})
    teams = pd.read_parquet(d / "teams.parquet")[["id", "code"]]
    pr = pd.read_parquet(d / "players_raw.parquet")[["id", "code", "first_name", "second_name", "web_name", "element_type"]]
    g = attach_team(g, fx)
    g = g.merge(pr.rename(columns={"id": "element"}), on="element", how="left", validate="many_to_one")
    if "position" in g:
        g["position"] = g["position"].replace(POS_FIX)
    else:
        g["position"] = g["element_type"].astype(int).map(POS_MAP)
    tmap = dict(zip(teams["id"], teams["code"]))
    g["team_code"] = g["team_id"].map(tmap)
    g["opponent_code"] = g["opp_id"].map(tmap)
    g["n_team_fixtures_gw"] = g.merge(team_fixture_counts(fx), left_on=["team_id", "gw"], right_on=["team", "gw"], how="left")["n"].values
    return g


def load_live() -> pd.DataFrame:
    d = latest_api_dir()
    events = pd.read_parquet(d / "events.parquet")
    finished = set(events.loc[_bool(events["finished"]), "id"].astype(int))
    h = pd.read_parquet(d / "element_history.parquet").drop_duplicates()
    h = h[h["round"].astype(int).isin(finished)].rename(columns={"round": "gw"})
    fx = pd.read_parquet(d / "fixtures.parquet").rename(columns={"id": "fixture", "event": "fixture_gw"})
    fx["fixture_gw"] = pd.to_numeric(fx["fixture_gw"]).astype("Int64")
    teams = pd.read_parquet(d / "teams.parquet")[["id", "code"]]
    el = pd.read_parquet(d / "elements.parquet")[["id", "code", "first_name", "second_name", "web_name", "element_type"]]
    h["gw"] = h["gw"].astype("Int64")
    h = attach_team(h, fx)
    h = h.merge(el.rename(columns={"id": "element"}), on="element", how="left", validate="many_to_one")
    h["position"] = h["element_type"].astype(int).map(POS_MAP)
    tmap = dict(zip(teams["id"], teams["code"]))
    h["team_code"] = h["team_id"].map(tmap)
    h["opponent_code"] = h["opp_id"].map(tmap)
    h["n_team_fixtures_gw"] = h.merge(team_fixture_counts(fx), left_on=["team_id", "gw"], right_on=["team", "gw"], how="left")["n"].values
    h["season"] = LIVE_SEASON
    return h


def team_fixture_counts(fx: pd.DataFrame) -> pd.DataFrame:
    f = fx.dropna(subset=["fixture_gw"])
    long = pd.concat([f[["team_h", "fixture_gw"]].rename(columns={"team_h": "team"}),
                      f[["team_a", "fixture_gw"]].rename(columns={"team_a": "team"})])
    long = long.rename(columns={"fixture_gw": "gw"}).astype({"team": int, "gw": int})
    return long.groupby(["team", "gw"]).size().rename("n").reset_index()


def season_team_codes() -> dict[str, set[int]]:
    out = {}
    for s in AUX_SEASONS:
        out[s] = set(pd.read_parquet(VAASTAV / s / "players_raw.parquet")["team_code"].astype(int))
    for s in HIST_SEASONS:
        out[s] = set(pd.read_parquet(VAASTAV / s / "teams.parquet")["code"].astype(int))
    out[LIVE_SEASON] = set(pd.read_parquet(latest_api_dir() / "teams.parquet")["code"].astype(int))
    return out


def season_player_teams() -> dict[str, dict[int, int]]:
    """season -> {player code: registered team code} from player lists (end-of-season team)."""
    out = {}
    for s in AUX_SEASONS + HIST_SEASONS:
        pr = pd.read_parquet(VAASTAV / s / "players_raw.parquet", columns=["code", "team_code"]).astype(int)
        out[s] = dict(zip(pr["code"], pr["team_code"]))
    el = pd.read_parquet(latest_api_dir() / "elements.parquet", columns=["code", "team_code"]).astype(int)
    out[LIVE_SEASON] = dict(zip(el["code"], el["team_code"]))
    return out


def classify_status(df: pd.DataFrame, seasons: list[str], registered: dict[str, dict[int, int]]) -> pd.DataFrame:
    """Per (player, season): returning / moved_pl_club / new_to_pl, plus mid_season_move, position_changed."""
    real = df[~df["is_ghost_fixture"]].sort_values(["season", "kickoff_time"])
    # main club = club with most GW rows in the season (ties -> later club). Season descriptor, not a feature.
    cnt = real.groupby(["player_id", "season", "team_code"]).agg(n=("gw", "size"), last=("kickoff_time", "max")).reset_index()
    main = cnt.sort_values(["n", "last"]).drop_duplicates(["player_id", "season"], keep="last")
    main = main.rename(columns={"team_code": "main_team"})[["player_id", "season", "main_team"]]
    ps = real.groupby(["player_id", "season"]).agg(
        last_team=("team_code", "last"),
        n_teams=("team_code", "nunique"), pos=("position", lambda s: s.mode().iloc[0]),
    ).reset_index().merge(main, on=["player_id", "season"])
    last_team = {(p, s): t for p, s, t in ps[["player_id", "season", "last_team"]].itertuples(index=False)}
    pos = {(p, s): v for p, s, v in ps[["player_id", "season", "pos"]].itertuples(index=False)}
    prev_of = dict(zip(seasons[1:], seasons[:-1]))
    status, pchg = [], []
    for p, s, first in ps[["player_id", "season", "main_team"]].itertuples(index=False):
        prev = prev_of.get(s)
        if prev is None or p not in registered.get(prev, {}):
            status.append("new_to_pl")
        else:
            prev_team = last_team.get((p, prev), registered[prev][p])
            status.append("returning" if prev_team == first else "moved_pl_club")
        pchg.append(bool(prev and (p, prev) in pos and pos[(p, prev)] != pos[(p, s)]))
    ps["player_status"] = status
    ps["mid_season_move"] = ps["n_teams"] > 1
    ps["position_changed"] = pchg
    return df.merge(ps[["player_id", "season", "player_status", "mid_season_move", "position_changed"]],
                    on=["player_id", "season"], how="left")


def build() -> pd.DataFrame:
    parts = [load_hist(s) for s in HIST_SEASONS] + [load_live()]
    df = pd.concat(parts, ignore_index=True)
    df = _num(df, STATS)
    df["player_id"] = df["code"].astype("Int64")
    df["price"] = df["value"] / 10
    df["is_dgw"] = df["n_team_fixtures_gw"] > 1

    # canonical team names keyed by stable team code (latest season's name wins)
    names = []
    for s in HIST_SEASONS:
        names.append(pd.read_parquet(VAASTAV / s / "teams.parquet")[["code", "name"]].assign(season=s))
    names.append(pd.read_parquet(latest_api_dir() / "teams.parquet")[["code", "name"]].assign(season=LIVE_SEASON))
    canon = pd.concat(names).sort_values("season").drop_duplicates("code", keep="last")
    cmap = dict(zip(canon["code"].astype(int), canon["name"]))
    df["team"] = df["team_code"].astype(int).map(cmap)
    df["opponent_team"] = df["opponent_code"].astype(int).map(cmap)

    team_codes = season_team_codes()
    seasons = AUX_SEASONS + HIST_SEASONS + [LIVE_SEASON]
    prev_of = dict(zip(seasons[1:], seasons[:-1]))
    df["promoted_team"] = [tc not in team_codes[prev_of[s]] for s, tc in zip(df["season"], df["team_code"].astype(int))]

    df = classify_status(df, seasons, season_player_teams())
    df["gw"] = df["gw"].astype(int)
    df = df[OUT_COLS].sort_values(["season", "gw", "kickoff_time", "player_id"]).reset_index(drop=True)
    return df
