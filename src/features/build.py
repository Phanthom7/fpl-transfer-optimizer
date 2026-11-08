"""Phase 3: leak-free player-GW features. One row per (player_id, season, gw).

Rule: a row for GW g uses only matches from GWs before g (merge_asof, strict), plus information
known before the GW g deadline (fixtures, price, pre-season team strength).
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from src.config import AUX_SEASONS, HIST_SEASONS, INTERIM_DIR, LIVE_SEASON, RAW_DIR
from src.features.spec import EWM_STATS, ROLL_STATS, WINDOWS

log = logging.getLogger(__name__)
SEASONS = HIST_SEASONS + [LIVE_SEASON]
S_IDX = {s: i for i, s in enumerate(SEASONS)}
VAASTAV = RAW_DIR / "vaastav"
API = RAW_DIR / "fpl_api" / LIVE_SEASON
FUTURE_GWS = 6        # live season: score this many GWs past the last finished one
PRIOR_K = 5           # blend weight = games / (games + K)
UPLIFT_FLAG = 1.10    # fixture type yields >= 10% above position average
OPP_GA_BINS = [-np.inf, 0.8, 1.2, 1.6, 2.0, np.inf]
SIGNING_PRICE = {"GK": 4.5, "DEF": 4.5, "MID": 5.0, "FWD": 5.0}


def tkey(season: pd.Series, gw: pd.Series) -> pd.Series:
    """Ordinal time key: strictly increasing across seasons and GWs."""
    return season.map(S_IDX).astype(int) * 100 + gw.astype(int)


def asof_before(left: pd.DataFrame, right: pd.DataFrame, by: str | list, cols: list[str],
                right_by: str | list | None = None) -> pd.DataFrame:
    """For each left row, take `cols` from the latest right row with t strictly < left t."""
    l = left[[*([by] if isinstance(by, str) else by), "t"]].reset_index().sort_values("t")
    rb = right_by or by
    r = right[[*([rb] if isinstance(rb, str) else rb), "t", *cols]].sort_values("t", kind="stable")
    if right_by:
        r = r.rename(columns=dict(zip([rb] if isinstance(rb, str) else rb, [by] if isinstance(by, str) else by)))
    m = pd.merge_asof(l, r, on="t", by=by, allow_exact_matches=False, direction="backward")
    return m.set_index("index")[cols].reindex(left.index)


# ---------------------------------------------------------------- inputs
def load_schedule() -> pd.DataFrame:
    """All fixtures, all seasons: season, gw, fixture, kickoff, home/away team codes, FDR, scores, finished."""
    parts = []
    for s in HIST_SEASONS:
        fx = pd.read_parquet(VAASTAV / s / "fixtures.parquet")
        tm = pd.read_parquet(VAASTAV / s / "teams.parquet")
        parts.append(_schedule(fx, tm, s))
    fx = pd.read_parquet(API / "fixtures.parquet")
    fx["gw"] = pd.to_numeric(fx["event"], errors="coerce")
    parts.append(_schedule(fx, pd.read_parquet(API / "teams.parquet"), LIVE_SEASON))
    return pd.concat(parts, ignore_index=True)


def _schedule(fx: pd.DataFrame, tm: pd.DataFrame, season: str) -> pd.DataFrame:
    code = dict(zip(tm["id"].astype(int), tm["code"].astype(int)))
    fx = fx.dropna(subset=["gw"]).copy()
    out = pd.DataFrame({
        "season": season, "gw": fx["gw"].astype(int), "fixture": fx["id"].astype(int),
        "kickoff_time": fx["kickoff_time"].astype(str),
        "home_code": fx["team_h"].astype(int).map(code), "away_code": fx["team_a"].astype(int).map(code),
        "fdr_h": pd.to_numeric(fx["team_h_difficulty"]), "fdr_a": pd.to_numeric(fx["team_a_difficulty"]),
        "h_score": pd.to_numeric(fx["team_h_score"], errors="coerce"),
        "a_score": pd.to_numeric(fx["team_a_score"], errors="coerce"),
        "finished": fx["finished"].astype(str).str.lower() == "true",
    })
    return out


def load_team_strength() -> pd.DataFrame:
    """Pre-season FPL strength ratings per season and team code (known before GW1)."""
    cols = ["code", "strength", "strength_attack_home", "strength_attack_away", "strength_defence_home",
            "strength_defence_away"]
    parts = [pd.read_parquet(VAASTAV / s / "teams.parquet")[cols].assign(season=s) for s in HIST_SEASONS]
    parts.append(pd.read_parquet(API / "teams.parquet")[cols].assign(season=LIVE_SEASON))
    out = pd.concat(parts, ignore_index=True).rename(columns={"code": "team_code"})
    for c in cols[1:]:
        out[c] = pd.to_numeric(out[c])
    return out


def load_player_gw() -> pd.DataFrame:
    pg = pd.read_parquet(INTERIM_DIR / "player_gw.parquet")
    pg = pg[~pg["is_ghost_fixture"].astype(bool) & (pg["position"] != "AM")].copy()
    pg["started"] = (pg["appearance"] == "started").astype(int)
    return pg


# ---------------------------------------------------------------- team state
def team_matches(schedule: pd.DataFrame, pg: pd.DataFrame) -> pd.DataFrame:
    """One row per (team, finished fixture) with goals, points and xG for/against."""
    f = schedule[schedule["finished"]]
    home = pd.DataFrame({"season": f.season, "gw": f.gw, "fixture": f.fixture, "kickoff_time": f.kickoff_time,
                         "team_code": f.home_code, "opp_code": f.away_code, "gf": f.h_score, "ga": f.a_score})
    away = pd.DataFrame({"season": f.season, "gw": f.gw, "fixture": f.fixture, "kickoff_time": f.kickoff_time,
                         "team_code": f.away_code, "opp_code": f.home_code, "gf": f.a_score, "ga": f.h_score})
    tm = pd.concat([home, away], ignore_index=True)
    tm["pts"] = np.select([tm.gf > tm.ga, tm.gf == tm.ga], [3, 1], 0)
    xg = pg.groupby(["season", "fixture", "team_code"])["expected_goals"].sum(min_count=1).rename("xgf").reset_index()
    tm = tm.merge(xg, on=["season", "fixture", "team_code"], how="left")
    opp_xg = xg.rename(columns={"team_code": "opp_code", "xgf": "xga"})
    tm = tm.merge(opp_xg, on=["season", "fixture", "opp_code"], how="left")
    tm = tm.sort_values(["team_code", "season", "kickoff_time"]).reset_index(drop=True)
    g = tm.groupby("team_code")
    for c in ["gf", "ga", "pts", "xgf", "xga"]:
        tm[f"{c}_r6"] = g[c].transform(lambda x: x.rolling(6, min_periods=1).mean())
    tm["t"] = tkey(tm["season"], tm["gw"])
    return tm


# ---------------------------------------------------------------- grid
def build_grid(pg: pd.DataFrame, schedule: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Player-GW grid + player-fixture context rows (incl. blank GWs and live future GWs)."""
    fix = pg[["player_id", "season", "gw", "fixture", "team_code", "opponent_code", "was_home"]].rename(
        columns={"opponent_code": "opp_code", "was_home": "home"})
    agg = {s: "sum" for s in ["total_points", "minutes", "expected_goals", "expected_assists", "bonus", "bps",
                              "ict_index", "clean_sheets", "goals_scored", "assists", "saves", "started"]}
    for s in ["expected_goals", "expected_assists"]:
        agg[s] = lambda x: x.sum(min_count=1)
    agg.update({"position": "first", "price": "first", "selected": "first", "transfers_balance": "first",
                "team_code": "last", "role": "first", "gws_at_club": "first", "apps_at_club": "first",
                "days_at_club": "first", "web_name": "first", "promoted_team": "first", "xP": "first"})
    gw = pg.sort_values("kickoff_time").groupby(["player_id", "season", "gw"]).agg(agg).reset_index()
    gw["n_fix"] = pg.groupby(["player_id", "season", "gw"]).size().values
    gw["finished"] = True

    # fill blank GWs inside each player-season span
    span = gw.groupby(["player_id", "season"])["gw"].agg(["min", "max"]).reset_index()
    full = span.loc[span.index.repeat(span["max"] - span["min"] + 1)].copy()
    full["gw"] = full.groupby(["player_id", "season"]).cumcount() + full["min"]
    grid = full[["player_id", "season", "gw"]].merge(gw, on=["player_id", "season", "gw"], how="left")
    blank = grid["n_fix"].isna()
    grid[["position", "team_code", "web_name", "price", "role"]] = grid.groupby(["player_id", "season"])[
        ["position", "team_code", "web_name", "price", "role"]].ffill()
    grid.loc[blank, ["n_fix", "total_points", "minutes", "started"]] = 0
    grid.loc[blank, "finished"] = True
    log.info("blank player-GW rows filled: %d", int(blank.sum()))

    fut, fut_fix = live_future_rows(gw, schedule)
    grid = pd.concat([grid, fut], ignore_index=True)
    fix = pd.concat([fix, fut_fix], ignore_index=True)
    grid["n_fix"] = grid["n_fix"].astype(int)
    grid["finished"] = grid["finished"].astype(bool)
    grid["t"] = tkey(grid["season"], grid["gw"])
    return grid.sort_values(["player_id", "t"]).reset_index(drop=True), fix


def live_future_rows(gw: pd.DataFrame, schedule: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Unfinished live GWs (current + next FUTURE_GWS-1) for every currently registered player."""
    ev = pd.read_parquet(API / "events.parquet")
    finished = ev.loc[ev["finished"].astype(str) == "True", "id"].astype(int)
    last = int(finished.max())
    gws = list(range(last + 1, min(last + FUTURE_GWS, 38) + 1))
    el = pd.read_parquet(API / "elements.parquet")
    pos = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}
    el = el[el["element_type"].astype(int).isin(pos)]
    base = pd.DataFrame({
        "player_id": el["code"].astype(int), "position": el["element_type"].astype(int).map(pos),
        "team_code": el["team_code"].astype(int), "web_name": el["web_name"],
        "price": pd.to_numeric(el["now_cost"]) / 10, "selected_pct": pd.to_numeric(el["selected_by_percent"]),
        "ep_next": pd.to_numeric(el["ep_next"], errors="coerce"),
        "chance_next": pd.to_numeric(el["chance_of_playing_next_round"], errors="coerce"),
        "fpl_status": el["status"],
    })
    rows = base.loc[base.index.repeat(len(gws))].copy()
    rows["gw"] = np.tile(gws, len(base))
    rows["season"] = LIVE_SEASON
    rows["finished"] = False
    next_gw = int(ev.loc[ev["is_next"].astype(str) == "True", "id"].iloc[0])
    nxt = rows["gw"] == next_gw  # ep_next / chance_of_playing_next_round describe the API's "next" GW only
    rows.loc[~nxt, ["ep_next", "chance_next"]] = np.nan
    s = schedule[(schedule["season"] == LIVE_SEASON) & schedule["gw"].isin(gws)]
    long = pd.concat([
        s.assign(team_code=s.home_code, opp_code=s.away_code, home=True),
        s.assign(team_code=s.away_code, opp_code=s.home_code, home=False)])[["gw", "fixture", "team_code", "opp_code", "home"]]
    fix = rows[["player_id", "season", "gw", "team_code"]].merge(long, on=["gw", "team_code"], how="inner")
    rows["n_fix"] = rows.merge(fix.groupby(["player_id", "gw"]).size().rename("n").reset_index(),
                               on=["player_id", "gw"], how="left")["n"].fillna(0).astype(int).values
    # carry leak-free club tenure / role from each player's latest finished row
    latest = gw[gw["season"] == LIVE_SEASON].sort_values("gw").groupby("player_id").tail(1)
    carry = latest.set_index("player_id")[["role", "promoted_team"]]
    rows = rows.join(carry, on="player_id")
    return rows.reset_index(drop=True), fix


# ---------------------------------------------------------------- player history features
def history_features(grid: pd.DataFrame, pl_min_2018: dict[int, float]) -> pd.DataFrame:
    """Rolling per-match rates over the player's previous matched GWs (any club, any season)."""
    h = grid[grid["finished"] & (grid["n_fix"] > 0)].copy()
    rate = {s: h[s] / h["n_fix"] for s in ROLL_STATS}
    h = h.assign(**{f"{s}_pm": v for s, v in rate.items()})
    g = h.groupby("player_id")
    out_cols = []
    for s in ROLL_STATS:
        for w in WINDOWS:
            c = f"{s}_r{w}"
            h[c] = g[f"{s}_pm"].transform(lambda x, w=w: x.rolling(w, min_periods=1).mean())
            out_cols.append(c)
    for s in EWM_STATS:
        h[f"{s}_ewm"] = g[f"{s}_pm"].transform(lambda x: x.ewm(span=5, min_periods=1).mean())
        out_cols.append(f"{s}_ewm")
    app = (h["minutes"] > 0).astype(int)
    h["mins0_share5"] = 1 - app.groupby(h["player_id"]).transform(lambda x: x.rolling(5, min_periods=1).mean())
    h["start_share5"] = h["started_r5"]
    h["last_minutes"] = h["minutes_pm"]
    h["games_played_in_PL"] = app.groupby(h["player_id"]).cumsum()
    h["pl_minutes_before"] = h.groupby("player_id")["minutes"].cumsum() + h["player_id"].map(pl_min_2018).fillna(0)
    out_cols += ["mins0_share5", "start_share5", "last_minutes", "games_played_in_PL", "pl_minutes_before"]

    feats = asof_before(grid, h, "player_id", out_cols)
    grid = grid.join(feats)
    grid["pl_minutes_before"] = grid["pl_minutes_before"].fillna(grid["player_id"].map(pl_min_2018)).fillna(0)
    grid["games_played_in_PL"] = grid["games_played_in_PL"].fillna(0)
    grid["form_trend"] = grid["total_points_r3"] - grid["total_points_r10"]

    # previous season per-match points/minutes (complete season, so known)
    ps = h.groupby(["player_id", "season"]).apply(
        lambda x: pd.Series({"ppm": x["total_points"].sum() / x["n_fix"].sum(),
                             "mpm": x["minutes"].sum() / x["n_fix"].sum()}), include_groups=False).reset_index()
    ps["season"] = ps["season"].map(lambda s: SEASONS[S_IDX[s] + 1] if S_IDX[s] + 1 < len(SEASONS) else None)
    ps = ps.dropna(subset=["season"]).rename(columns={"ppm": "prev_season_ppm", "mpm": "prev_season_mpm"})
    return grid.merge(ps, on=["player_id", "season"], how="left")


def tenure_features(grid: pd.DataFrame) -> pd.DataFrame:
    """Club tenure: from Phase 2 (prior-only) on matched rows; future rows extend from latest."""
    for c in ["gws_at_club", "apps_at_club", "days_at_club"]:
        grid[c] = grid.groupby(["player_id", "team_code"])[c].ffill()
    return grid


# ---------------------------------------------------------------- context
def context_features(grid: pd.DataFrame, fix: pd.DataFrame, schedule: pd.DataFrame, tm: pd.DataFrame,
                     strength: pd.DataFrame, pg: pd.DataFrame) -> pd.DataFrame:
    sch = schedule.set_index(["season", "fixture"])
    fix = fix.join(sch[["fdr_h", "fdr_a"]], on=["season", "fixture"])
    fix["home"] = fix["home"].astype(bool)
    fix["fdr"] = np.where(fix["home"], fix["fdr_h"], fix["fdr_a"])
    fix["t"] = tkey(fix["season"], fix["gw"])
    fix = fix.reset_index(drop=True)
    tcols = ["gf_r6", "ga_r6", "pts_r6", "xgf_r6", "xga_r6"]
    own = asof_before(fix, tm, "team_code", tcols)
    opp = asof_before(fix, tm, "opp_code", tcols, right_by="team_code")
    fix = fix.join(own.add_prefix("team_")).join(opp.add_prefix("opp_"))
    st = strength.set_index(["season", "team_code"])
    o = st.reindex(pd.MultiIndex.from_arrays([fix["season"], fix["opp_code"]])).reset_index(drop=True)
    t = st.reindex(pd.MultiIndex.from_arrays([fix["season"], fix["team_code"]])).reset_index(drop=True)
    # opponent plays away when we are home
    fix["opp_str_def"] = np.where(fix["home"], o["strength_defence_away"], o["strength_defence_home"])
    fix["opp_str_att"] = np.where(fix["home"], o["strength_attack_away"], o["strength_attack_home"])
    fix["team_str_att"] = np.where(fix["home"], t["strength_attack_home"], t["strength_attack_away"])
    fix["team_str_def"] = np.where(fix["home"], t["strength_defence_home"], t["strength_defence_away"])

    # high-scoring fixture type: (position, home, opponent goals-against bucket), from previous seasons only
    pos = grid.drop_duplicates(["player_id", "season", "gw"]).set_index(["player_id", "season", "gw"])["position"]
    fix["position"] = pos.reindex(pd.MultiIndex.from_frame(fix[["player_id", "season", "gw"]])).values
    fix["opp_bucket"] = pd.cut(fix["opp_ga_r6"], OPP_GA_BINS, labels=False)
    fix = fix.join(fixture_uplift(fix, pg), on=["season", "position", "home", "opp_bucket"])
    fix["high_scoring_fixture"] = (fix["fixture_uplift"] >= UPLIFT_FLAG).astype(float).where(fix["fixture_uplift"].notna())

    agg = fix.groupby(["player_id", "season", "gw"]).agg(
        home_share=("home", "mean"), fdr=("fdr", "mean"),
        opp_ga_r6=("opp_ga_r6", "mean"), opp_gf_r6=("opp_gf_r6", "mean"), opp_xga_r6=("opp_xga_r6", "mean"),
        opp_xgf_r6=("opp_xgf_r6", "mean"), opp_pts_r6=("opp_pts_r6", "mean"),
        opp_str_def=("opp_str_def", "mean"), opp_str_att=("opp_str_att", "mean"),
        team_gf_r6=("team_gf_r6", "mean"), team_ga_r6=("team_ga_r6", "mean"), team_xgf_r6=("team_xgf_r6", "mean"),
        team_pts_r6=("team_pts_r6", "mean"), team_str_att=("team_str_att", "mean"),
        team_str_def=("team_str_def", "mean"), fixture_uplift=("fixture_uplift", "mean"),
        high_scoring_fixture=("high_scoring_fixture", "max"),
    ).reset_index()
    grid = grid.merge(agg, on=["player_id", "season", "gw"], how="left")
    grid["is_dgw"] = (grid["n_fix"] > 1).astype(int)
    grid["is_bgw"] = (grid["n_fix"] == 0).astype(int)

    # next 3 / 5 GWs (inclusive of g): from the fixture list (known in advance), for the row's current club
    grid = grid.merge(team_schedule_ahead(schedule), on=["season", "team_code", "gw"], how="left")
    return grid


def team_schedule_ahead(schedule: pd.DataFrame) -> pd.DataFrame:
    """Per (season, team, gw): fixture count and mean FDR over gw..gw+k-1, k in (3, 5)."""
    long = pd.concat([
        schedule.assign(team_code=schedule.home_code, fdr=schedule.fdr_h),
        schedule.assign(team_code=schedule.away_code, fdr=schedule.fdr_a)])
    per = long.groupby(["season", "team_code", "gw"]).agg(n=("fixture", "size"), f=("fdr", "sum")).reset_index()
    teams = per[["season", "team_code"]].drop_duplicates()
    full = teams.loc[teams.index.repeat(38)].assign(gw=np.tile(np.arange(1, 39), len(teams)))
    full = full.merge(per, on=["season", "team_code", "gw"], how="left").fillna({"n": 0, "f": 0})
    full = full.sort_values(["season", "team_code", "gw"])
    g = full.groupby(["season", "team_code"])
    for k in (3, 5):
        n = g["n"].transform(lambda x, k=k: x[::-1].rolling(k, min_periods=1).sum()[::-1])
        f = g["f"].transform(lambda x, k=k: x[::-1].rolling(k, min_periods=1).sum()[::-1])
        full[f"n_fix_next{k}"] = n
        full[f"fdr_next{k}"] = f / n.replace(0, np.nan)
    return full.drop(columns=["n", "f"])


def fixture_uplift(fix: pd.DataFrame, pg: pd.DataFrame) -> pd.Series:
    """Points per played match by fixture type / position average, using seasons strictly before."""
    played = pg[pg["minutes"] > 0][["player_id", "season", "fixture", "total_points"]]
    f = fix[fix["season"].isin(HIST_SEASONS)].merge(played, on=["player_id", "season", "fixture"])
    f = f.dropna(subset=["opp_bucket"])
    by_type = f.groupby(["season", "position", "home", "opp_bucket"])["total_points"].agg(["sum", "count"])
    by_pos = f.groupby(["season", "position"])["total_points"].agg(["sum", "count"])
    rows = []
    for s in SEASONS:
        have = set(by_type.index.get_level_values(0))
        prev = [x for x in HIST_SEASONS if S_IDX[x] < S_IDX[s] and x in have]
        if not prev:
            continue
        bt = by_type.loc[prev].groupby(level=[1, 2, 3]).sum()
        bp = by_pos.loc[prev].groupby(level=1).sum()
        u = (bt["sum"] / bt["count"]) / (bp["sum"] / bp["count"]).reindex(bt.index.get_level_values(0)).values
        u = u[bt["count"] >= 30]
        rows.append(u.rename("fixture_uplift").reset_index().assign(season=s))
    out = pd.concat(rows).set_index(["season", "position", "home", "opp_bucket"])["fixture_uplift"]
    return out


# ---------------------------------------------------------------- market
def market_features(grid: pd.DataFrame) -> pd.DataFrame:
    g = grid.groupby(["player_id", "season"])
    grid["price"] = g["price"].ffill()
    grid["price_change3"] = grid["price"] - g["price"].shift(3)
    rank = grid.groupby(["season", "gw"])["selected"].rank(pct=True)
    live_rank = grid.groupby(["season", "gw"])["selected_pct"].rank(pct=True) if "selected_pct" in grid else rank
    grid["selected_rank"] = rank.fillna(live_rank)
    grid["selected_rank_lag1"] = g["selected_rank"].shift(1)
    grid["transfers_balance_lag1"] = g["transfers_balance"].shift(1)
    # live future rows: latest known ownership rank carries forward
    fut = ~grid["finished"]
    grid.loc[fut, "selected_rank_lag1"] = grid.loc[fut, "selected_rank"]
    return grid


# ---------------------------------------------------------------- cold start
def status_asof(grid: pd.DataFrame, registered: dict[str, dict[int, int]], played: dict[str, set]) -> pd.Series:
    """Row-level status using only what is known at the row: last season's registration/club, this row's club."""
    prev_of = {s: p for p, s in zip(AUX_SEASONS + SEASONS, SEASONS)}
    out = []
    first_price = grid.groupby(["player_id", "season"])["price"].transform("first")
    for p, s, tc, promoted, pos, fp in zip(grid["player_id"], grid["season"], grid["team_code"],
                                          grid["promoted_team"], grid["position"], first_price):
        prev = prev_of[s]
        if p in registered[prev]:
            out.append("returning" if registered[prev][p] == tc else "moved_pl_club")
            continue
        earlier = [x for x in (AUX_SEASONS + SEASONS)[:(AUX_SEASONS + SEASONS).index(prev)]]
        if any(p in played.get(x, ()) for x in earlier):
            out.append("returned_to_pl")
        elif promoted is True or promoted == 1:
            out.append("new_promoted_club")
        elif fp >= SIGNING_PRICE.get(pos, 99):
            out.append("new_signing")
        else:
            out.append("new_fringe")
    return pd.Series(out, index=grid.index)


def cold_start(grid: pd.DataFrame, strength: pd.DataFrame) -> pd.DataFrame:
    """Priors by (position, price bracket, team strength), fit on previous seasons only; blend by games played."""
    st = strength.set_index(["season", "team_code"])["strength"]
    grid["team_strength"] = st.reindex(pd.MultiIndex.from_arrays([grid["season"], grid["team_code"]])).values
    grid["price_bracket"] = (np.floor(grid["price"] * 2) / 2).clip(upper=10)
    grid["str_bucket"] = pd.cut(grid["team_strength"], [0, 2.5, 3.5, 9], labels=False)
    done = grid[grid["finished"] & (grid["n_fix"] > 0)]
    keys = ["position", "price_bracket", "str_bucket"]
    rows = []
    for s in SEASONS:
        prev = done[done["season"].map(S_IDX) < S_IDX[s]]
        if prev.empty:
            continue
        a = prev.groupby(keys).agg(pts=("total_points", "sum"), mins=("minutes", "sum"), n=("n_fix", "sum"))
        b = prev.groupby("position").agg(pts=("total_points", "sum"), mins=("minutes", "sum"), n=("n_fix", "sum"))
        a = a[a["n"] >= 50]
        tab = (a[["pts", "mins"]].div(a["n"], axis=0)).rename(columns={"pts": "prior_ppm", "mins": "prior_mpm"})
        pos_tab = (b[["pts", "mins"]].div(b["n"], axis=0)).rename(columns={"pts": "pos_ppm", "mins": "pos_mpm"})
        rows.append((s, tab, pos_tab))
    grid["prior_ppm"] = np.nan
    grid["prior_mpm"] = np.nan
    for s, tab, pos_tab in rows:
        m = grid["season"] == s
        sub = grid.loc[m, keys].join(tab, on=keys).join(pos_tab, on="position")
        grid.loc[m, "prior_ppm"] = sub["prior_ppm"].fillna(sub["pos_ppm"]).values
        grid.loc[m, "prior_mpm"] = sub["prior_mpm"].fillna(sub["pos_mpm"]).values
    w = grid["games_played_in_PL"] / (grid["games_played_in_PL"] + PRIOR_K)
    grid["prior_weight"] = 1 - w
    for out, roll, prior in [("pts_r5_blend", "total_points_r5", "prior_ppm"), ("mins_r5_blend", "minutes_r5", "prior_mpm")]:
        r = grid[roll]
        grid[out] = np.where(r.notna(), w * r + (1 - w) * grid[prior], grid[prior])
    return grid.drop(columns=["price_bracket", "str_bucket"])


# ---------------------------------------------------------------- targets
def targets(grid: pd.DataFrame) -> pd.DataFrame:
    g = grid.groupby(["player_id", "season"])
    pts = grid["total_points"].where(grid["finished"])
    grid["y_1"] = pts
    for k in (3, 5):
        fwd = pts.groupby([grid["player_id"], grid["season"]]).transform(
            lambda x, k=k: x[::-1].rolling(k, min_periods=k).sum()[::-1])
        grid[f"y_{k}"] = fwd
    return grid


# ---------------------------------------------------------------- main
def registered_and_played(pg: pd.DataFrame) -> tuple[dict, dict, dict]:
    reg, played, min18 = {}, {}, {}
    for s in AUX_SEASONS + HIST_SEASONS:
        pr = pd.read_parquet(VAASTAV / s / "players_raw.parquet", columns=["code", "team_code", "minutes"])
        pr = pr.astype({"code": int, "team_code": int})
        reg[s] = dict(zip(pr["code"], pr["team_code"]))
        if s in AUX_SEASONS:
            played[s] = set(pr.loc[pd.to_numeric(pr["minutes"]) > 0, "code"])
            min18 = dict(zip(pr["code"], pd.to_numeric(pr["minutes"])))
    el = pd.read_parquet(API / "elements.parquet", columns=["code", "team_code"]).astype(int)
    reg[LIVE_SEASON] = dict(zip(el["code"], el["team_code"]))
    for s, g in pg[pg["minutes"] > 0].groupby("season"):  # noqa: B007
        played[s] = set(g["player_id"].astype(int))
    return reg, played, min18


def build(pg: pd.DataFrame | None = None, schedule: pd.DataFrame | None = None) -> pd.DataFrame:
    """Inputs injectable so evals can rebuild on truncated data."""
    pg = load_player_gw() if pg is None else pg
    schedule = load_schedule() if schedule is None else schedule
    strength = load_team_strength()
    reg, played, min18 = registered_and_played(pg)
    grid, fix = build_grid(pg, schedule)
    grid = history_features(grid, min18)
    grid = tenure_features(grid)
    grid = context_features(grid, fix, schedule, team_matches(schedule, pg), strength, pg).copy()
    grid = market_features(grid)
    grid["promoted_team"] = grid.groupby(["player_id", "season"])["promoted_team"].transform(
        lambda x: x.ffill().bfill()).fillna(False).astype(bool)
    grid["status_asof"] = status_asof(grid, reg, played)
    grid = cold_start(grid, strength).copy()
    grid = targets(grid)
    grid["fpl_xp"] = grid["xP"].fillna(grid["ep_next"]) if "ep_next" in grid else grid["xP"]
    grid = grid.drop(columns=["xP", "selected", "selected_rank", "transfers_balance", "t"], errors="ignore")
    return grid.sort_values(["season", "gw", "player_id"]).reset_index(drop=True)
