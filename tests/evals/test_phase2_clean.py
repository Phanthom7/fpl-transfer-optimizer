"""Phase 2 evals: clean player-GW table. Expected to FAIL until Phase 2 is built.

Contract: data/interim/player_gw.parquet, one row per (player, season, gw, fixture), columns:
season, gw, player_id, code, element, fixture, team, opponent_team, position, total_points, minutes,
first_name, second_name, web_name, player_status, promoted_team
"""
import pandas as pd
import pytest

from src import config
from src.ingest.historical import OUT as VAASTAV

INTERIM = config.INTERIM_DIR / "player_gw.parquet"
KEY = ["player_id", "season", "gw", "fixture"]
NON_NULL = ["total_points", "minutes", "team", "position"]


@pytest.fixture(scope="module")
def pg():
    assert INTERIM.exists(), f"Phase 2 not built: {INTERIM} missing"
    return pd.read_parquet(INTERIM)


def api_dir():
    return sorted(p for p in (config.RAW_DIR / "fpl_api").glob("*") if p.is_dir())[-1]


def raw_points() -> pd.DataFrame:
    """Raw per (season, element, gw) points. Exact duplicate source rows dropped."""
    parts = []
    for s in config.HIST_SEASONS:
        g = pd.read_parquet(VAASTAV / s / "merged_gw.parquet").drop_duplicates()
        parts.append(g[["season", "element", "gw", "total_points"]])
    d = api_dir()
    ev = pd.read_parquet(d / "events.parquet")
    fin = set(ev.loc[ev["finished"].astype(str) == "True", "id"].astype(int))
    h = pd.read_parquet(d / "element_history.parquet").drop_duplicates()
    h = h[h["round"].astype(int).isin(fin)]
    parts.append(pd.DataFrame({"season": config.LIVE_SEASON, "element": h["element"], "gw": h["round"], "total_points": h["total_points"]}))
    raw = pd.concat(parts)
    raw = raw.astype({"element": int, "gw": int, "total_points": int})
    return raw.groupby(["season", "element", "gw"], as_index=False)["total_points"].sum()


def season_codes(season: str) -> dict[int, int]:
    """element -> code from raw player lists, only for players with GW rows."""
    if season == config.LIVE_SEASON:
        d = api_dir()
        el = pd.read_parquet(d / "elements.parquet", columns=["id", "code"])
        played = set(pd.read_parquet(d / "element_history.parquet", columns=["element"])["element"].astype(int))
    else:
        el = pd.read_parquet(VAASTAV / season / "players_raw.parquet", columns=["id", "code"])
        played = set(pd.read_parquet(VAASTAV / season / "merged_gw.parquet", columns=["element"])["element"].astype(int))
    el = el.astype(int)
    return {e: c for e, c in zip(el["id"], el["code"]) if e in played}


def returning_match_rate(pg) -> tuple[float, int, int]:
    ids = pg[["season", "element", "player_id"]].drop_duplicates().astype({"element": int})
    lut = {(s, e): p for s, e, p in ids.itertuples(index=False)}
    matched = total = 0
    seasons = config.ALL_SEASONS
    for prev, cur in zip(seasons, seasons[1:]):
        a = {c: e for e, c in season_codes(prev).items()}
        b = {c: e for e, c in season_codes(cur).items()}
        for code in set(a) & set(b):
            total += 1
            p1, p2 = lut.get((prev, a[code])), lut.get((cur, b[code]))
            matched += int(p1 is not None and pd.notna(p1) and p1 == p2)
    return matched / max(total, 1), matched, total


@pytest.mark.critical
def test_no_duplicate_keys(pg, ev):
    """Zero duplicate (player, season, GW, fixture) keys"""
    d = int(pg.duplicated(KEY).sum())
    ev.check(d == 0, d, "0")


@pytest.mark.critical
def test_no_nulls_core(pg, ev):
    """Zero nulls in points, minutes, team, position"""
    nulls = {c: int(pg[c].isna().sum()) if c in pg else -1 for c in NON_NULL}
    ev.check(all(v == 0 for v in nulls.values()), nulls, "all 0 (-1 = column missing)")


@pytest.mark.critical
def test_points_reconcile(pg, ev):
    """Points per GW reconcile 100% to raw"""
    raw = raw_points()
    mine = pg.astype({"element": int, "gw": int}).groupby(["season", "element", "gw"], as_index=False)["total_points"].sum()
    m = raw.merge(mine, on=["season", "element", "gw"], how="outer", suffixes=("_raw", "_pg"), indicator=True)
    ok = (m["_merge"] == "both") & (m["total_points_raw"] == m["total_points_pg"])
    rate = ok.mean()
    ev.check(rate == 1.0, rate, "1.0",
             f"raw_only={int((m._merge == 'left_only').sum())} pg_only={int((m._merge == 'right_only').sum())} mismatch={int(((m._merge == 'both') & ~ok).sum())}")


@pytest.mark.pass_gate
def test_returning_matched_98(pg, ev):
    """98%+ returning players matched across seasons"""
    rate, m, n = returning_match_rate(pg)
    ev.check(rate >= 0.98, rate, ">= 0.98", f"{m}/{n}")


@pytest.mark.good
def test_returning_matched_995(pg, ev):
    """99.5%+ returning players matched across seasons"""
    rate, m, n = returning_match_rate(pg)
    ev.check(rate >= 0.995, rate, ">= 0.995", f"{m}/{n}")


# (tokens, anchor season, {season: team or None=absent}, {season: status}, {season: promoted_team})
KNOWN = [
    (("mohamed", "salah"), "2019-20", {s: "Liverpool" for s in config.HIST_SEASONS}, {"2023-24": "returning"}, {}),
    (("declan", "rice"), "2022-23", {"2022-23": "West Ham", "2023-24": "Arsenal"}, {"2023-24": "moved_pl_club"}, {}),
    (("erling", "haaland"), "2022-23", {"2021-22": None, "2022-23": "Man City"}, {"2022-23": "new_to_pl"}, {}),
    (("kai", "havertz"), "2022-23", {"2022-23": "Chelsea", "2023-24": "Arsenal"}, {"2023-24": "moved_pl_club"}, {}),
    (("cole", "palmer"), "2022-23", {"2022-23": "Man City", "2023-24": "Chelsea"}, {"2023-24": "moved_pl_club"}, {}),
    (("martin", "degaard"), "2021-22", {s: "Arsenal" for s in config.HIST_SEASONS[1:]}, {"2021-22": "returning"}, {}),
    (("bruno", "fernandes"), "2020-21", {"2019-20": "Man Utd", "2025-26": "Man Utd"}, {"2020-21": "returning"}, {}),
    (("heung", "son"), "2019-20", {"2019-20": "Spurs", "2024-25": "Spurs"}, {"2024-25": "returning"}, {}),  # first/second name swap in raw from 2022-23
    (("aleksandar", "mitrovi"), "2020-21", {"2020-21": "Fulham", "2021-22": None, "2022-23": "Fulham"}, {}, {"2020-21": True, "2022-23": True}),
    (("viktor", "gy"), "2025-26", {"2024-25": None, "2025-26": "Arsenal"}, {"2025-26": "new_to_pl"}, {}),
]


@pytest.mark.good
def test_spot_check_known_players(pg, ev):
    """10 known players spot-checked (club movers, new signings, name swap, gap season)"""
    full = (pg["first_name"].fillna("") + " " + pg["second_name"].fillna("")).str.lower()
    fails = []
    for tokens, anchor, teams, statuses, promoted in KNOWN:
        hit = pg[(pg["season"] == anchor) & full.apply(lambda n: all(t in n for t in tokens))]
        if hit["player_id"].nunique() != 1:
            fails.append(f"{tokens[1]}: {hit['player_id'].nunique()} ids in {anchor}")
            continue
        rows = pg[pg["player_id"] == hit["player_id"].iloc[0]]
        for s, team in teams.items():
            got = rows.loc[rows["season"] == s, "team"]
            if team is None and len(got):
                fails.append(f"{tokens[1]} {s}: expected absent, got {got.mode().iloc[0]}")
            elif team is not None and (not len(got) or got.mode().iloc[0] != team):
                fails.append(f"{tokens[1]} {s}: expected {team}, got {got.mode().iloc[0] if len(got) else 'absent'}")
        for s, st in statuses.items():
            got = rows.loc[rows["season"] == s, "player_status"].unique().tolist()
            if got != [st]:
                fails.append(f"{tokens[1]} {s}: status {got} != {st}")
        for s, pr in promoted.items():
            got = rows.loc[rows["season"] == s, "promoted_team"].unique().tolist()
            if got != [pr]:
                fails.append(f"{tokens[1]} {s}: promoted {got} != {pr}")
    ev.check(not fails, f"{len(KNOWN) - len({f.split()[0].rstrip(':') for f in fails})}/{len(KNOWN)}", "10/10", "; ".join(fails))


# ---- Added after user review: role / tenure / status_detail (pending approval) ----
from src.clean import roles as _roles

ROLE_SET = {"starter", "substitute", "benchwarmer", "unknown"}
DETAIL_SET = {"returning", "moved_pl_club", "returned_to_pl", "new_promoted_club", "new_signing", "new_fringe"}


@pytest.mark.critical
def test_role_tenure_leak_free(pg, ev):
    """role + tenure use only earlier matches (truncate-and-recompute, 200 rows)"""
    cols = ["role", "starts_last5", "apps_last5", "gws_at_club", "apps_at_club", "days_at_club"]
    real = pg[~pg["is_ghost_fixture"].astype(bool)]
    sample = real.sample(200, random_state=7)
    bad = 0
    for _, row in sample.iterrows():
        hist = real[(real["player_id"] == row["player_id"]) & (real["kickoff_time"] <= row["kickoff_time"])].copy()
        # wipe the target row's own outcome: recomputed features must not change
        mask = (hist["kickoff_time"] == row["kickoff_time"]) & (hist["fixture"] == row["fixture"])
        hist.loc[mask, ["minutes", "starts"]] = [0, 0]
        re = _roles.add_roles(hist.drop(columns=cols + ["appearance", "role_season"]))
        got = re.loc[(re["fixture"] == row["fixture"]) & (re["kickoff_time"] == row["kickoff_time"]), cols].iloc[0]
        bad += int(any(str(got[c]) != str(row[c]) for c in cols))
    ev.check(bad == 0, f"{200 - bad}/200", "200/200")


@pytest.mark.pass_gate
def test_role_and_detail_valid(pg, ev):
    """role, role_season, status_detail populated with valid labels"""
    real = pg[~pg["is_ghost_fixture"].astype(bool)]
    bad_role = int((~real["role"].isin(ROLE_SET)).sum())
    bad_season = int((~real["role_season"].isin(ROLE_SET - {"unknown"})).sum())
    bad_detail = int((~real["status_detail"].isin(DETAIL_SET)).sum())
    consistent = int(((real["player_status"] == "new_to_pl") != real["status_detail"].isin(
        {"returned_to_pl", "new_promoted_club", "new_signing", "new_fringe"})).sum())
    ev.check(bad_role + bad_season + bad_detail + consistent == 0,
             f"bad_role={bad_role} bad_role_season={bad_season} bad_detail={bad_detail} inconsistent={consistent}", "all 0")


@pytest.mark.good
def test_role_separates_points(pg, ev):
    """Mean points: starter > substitute > benchwarmer (every season)"""
    real = pg[~pg["is_ghost_fixture"].astype(bool) & (pg["position"] != "AM")]
    m = real.groupby(["season", "role"])["total_points"].mean().unstack()
    ok = ((m["starter"] > m["substitute"]) & (m["substitute"] > m["benchwarmer"])).all()
    ev.check(bool(ok), f"starter={m['starter'].mean():.2f} sub={m['substitute'].mean():.2f} bench={m['benchwarmer'].mean():.2f}", "strict order all seasons")
