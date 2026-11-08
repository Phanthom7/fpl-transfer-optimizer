"""Phase 3 evals: leak-free features. Real data."""
import numpy as np
import pandas as pd
import pytest

from src import config
from src.features import build as fb
from src.features.spec import COLD_CORE, FEATURES, TARGETS

FEAT = config.PROCESSED_DIR / "features.parquet"
OUTCOME = ["total_points", "minutes", "starts", "goals_scored", "assists", "clean_sheets", "goals_conceded",
           "own_goals", "penalties_saved", "penalties_missed", "yellow_cards", "red_cards", "saves", "bonus", "bps",
           "influence", "creativity", "threat", "ict_index", "expected_goals", "expected_assists",
           "expected_goal_involvements", "expected_goals_conceded", "defensive_contribution",
           "clearances_blocks_interceptions", "recoveries", "tackles", "team_h_score", "team_a_score"]
CUTOFFS = [("2021-22", 20), ("2023-24", 8), ("2024-25", 30), ("2025-26", 15)]


@pytest.fixture(scope="module")
def feats():
    assert FEAT.exists(), "Phase 3 not built"
    return pd.read_parquet(FEAT)


def truncated_inputs(season: str, gw: int):
    """Everything from (season, gw) on is unknown: later rows dropped, GW g outcomes wiped, results hidden."""
    pg = fb.load_player_gw()
    sch = fb.load_schedule()
    t = fb.tkey(pg["season"], pg["gw"])
    cut = fb.tkey(pd.Series([season]), pd.Series([gw]))[0]
    pg = pg[t <= cut].copy()
    at = fb.tkey(pg["season"], pg["gw"]) == cut
    cols = [c for c in OUTCOME if c in pg]
    pg.loc[at, cols] = 0
    pg.loc[at, "appearance"] = "unused"
    pg.loc[at, "started"] = 0
    st = fb.tkey(sch["season"], sch["gw"]) >= cut
    sch.loc[st, ["h_score", "a_score"]] = np.nan
    sch.loc[st, "finished"] = False
    return pg, sch


def same(a, b) -> bool:
    if pd.isna(a) and pd.isna(b):
        return True
    if isinstance(a, (float, int, np.floating, np.integer)) and isinstance(b, (float, int, np.floating, np.integer)):
        return bool(np.isclose(a, b, rtol=1e-9, atol=1e-9))
    return str(a) == str(b)


@pytest.mark.critical
def test_no_leakage_truncate_recompute(feats, ev):
    """Leakage: features for 200 player-GWs identical when all data from that GW on is removed"""
    bad, n, detail = 0, 0, []
    for season, gw in CUTOFFS:
        full = feats[(feats["season"] == season) & (feats["gw"] == gw) & (feats["n_fix"] > 0)]
        sample = full.sample(50, random_state=gw)
        trunc = fb.build(*truncated_inputs(season, gw))
        trunc = trunc[(trunc["season"] == season) & (trunc["gw"] == gw)].set_index("player_id")
        for _, row in sample.iterrows():
            n += 1
            other = trunc.loc[row["player_id"]]
            diff = [c for c in FEATURES if not same(row[c], other[c])]
            if diff:
                bad += 1
                detail.append(f"{season} gw{gw} {row['player_id']}: {diff[:4]}")
    ev.check(bad == 0, f"{n - bad}/{n}", "200/200", "; ".join(detail[:5]))


@pytest.mark.critical
def test_no_target_stats_in_features(feats, ev):
    """No same-GW outcome stats in features (names + |spearman| > 0.95 with y_1 / same-GW minutes)"""
    named = [c for c in FEATURES if c in OUTCOME or c in TARGETS]
    d = feats[feats["finished"] & (feats["n_fix"] > 0) & (feats["season"] >= "2020-21")]
    num = [c for c in FEATURES if pd.api.types.is_numeric_dtype(d[c])]
    rho_y = d[num].corrwith(d["y_1"], method="spearman").abs()
    rho_m = d[num].corrwith(d["minutes"], method="spearman").abs()
    leaked = sorted(set(rho_y[rho_y > 0.95].index) | set(rho_m[rho_m > 0.95].index) | set(named))
    ev.check(not leaked, len(leaked), "0", f"{leaked} max|rho| y={rho_y.max():.3f} min={rho_m.max():.3f}")


@pytest.mark.critical
def test_rolling_matches_hand_calc(feats, ev):
    """Rolling 3/5/10 (points, minutes) match hand calc for 20 players"""
    f = feats.sort_values(["player_id", "season", "gw"])
    ids = f.loc[f["season"] >= "2022-23", "player_id"].drop_duplicates().sample(20, random_state=3)
    order = {s: i for i, s in enumerate(fb.SEASONS)}
    bad = checked = 0
    for pid in ids:
        rows = f[f["player_id"] == pid]
        hist = []  # (per-match points, per-match minutes) of previous matched, finished GWs
        for _, r in rows.iterrows():
            for w in (3, 5, 10):
                last = hist[-w:]
                exp_p = np.mean([h[0] for h in last]) if last else np.nan
                exp_m = np.mean([h[1] for h in last]) if last else np.nan
                checked += 2
                bad += int(not same(exp_p, r[f"total_points_r{w}"])) + int(not same(exp_m, r[f"minutes_r{w}"]))
            if r["finished"] and r["n_fix"] > 0:
                hist.append((r["total_points"] / r["n_fix"], r["minutes"] / r["n_fix"]))
    ev.check(bad == 0, f"{checked - bad}/{checked} values", "100%")


@pytest.mark.pass_gate
def test_cold_start_prior_filled(feats, ev):
    """Cold-start rows (games_played_in_PL < 3) have prior-filled features (2020-21 on)"""
    cold = feats[(feats["games_played_in_PL"] < 3) & (feats["season"] >= "2020-21")]
    nulls = cold[COLD_CORE].isna().sum()
    ev.check(int(nulls.sum()) == 0, f"{len(cold)} rows, nulls={nulls.to_dict()}", "100% non-null")


@pytest.mark.pass_gate
def test_games_played_monotone(feats, ev):
    """games_played_in_PL monotone non-decreasing per player"""
    f = feats.assign(t=fb.tkey(feats["season"], feats["gw"])).sort_values(["player_id", "t"])
    dec = int((f.groupby("player_id")["games_played_in_PL"].diff() < 0).sum())
    ev.check(dec == 0, f"{dec} decreases", "0")


@pytest.mark.good
def test_rolling5_spearman_next_gw(feats, ev):
    """Rolling-5 points Spearman with next-GW points"""
    d = feats[feats["y_1"].notna() & (feats["season"] >= "2020-21")]
    rho = d["total_points_r5"].corr(d["y_1"], method="spearman")
    ev.check(rho >= 0.30, rho, ">= 0.30")
