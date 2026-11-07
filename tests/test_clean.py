import pandas as pd
import pytest

from src.clean.build import attach_team, classify_status, team_fixture_counts
from src.ingest.gw import normalize_gw

FX = pd.DataFrame({"fixture": [1, 2, 3], "team_h": [10, 30, 10], "team_a": [20, 10, 40], "fixture_gw": [1, 2, 2]})


def test_team_from_fixture_and_home_flag():
    rows = pd.DataFrame({"fixture": [1, 2], "was_home": ["True", "False"], "gw": [1, 2], "opponent_team": [20, 30]})
    out = attach_team(rows, FX)
    assert out["team_id"].tolist() == [10, 10]
    assert out["opp_id"].tolist() == [20, 30]
    assert not out["is_ghost_fixture"].any()


def test_opponent_mismatch_raises():
    rows = pd.DataFrame({"fixture": [1], "was_home": [True], "gw": [1], "opponent_team": [99]})
    with pytest.raises(ValueError):
        attach_team(rows, FX)


def test_ghost_row_flagged():
    rows = pd.DataFrame({"fixture": [1], "was_home": [True], "gw": [5]})  # listed in wrong GW
    assert attach_team(rows, FX)["is_ghost_fixture"].iloc[0]


def test_covid_gw_remap():
    assert normalize_gw("2019-20", pd.Series([29, 39, 47])).tolist() == [29, 30, 38]
    assert normalize_gw("2020-21", pd.Series([39])).tolist() == [39]


def test_dgw_counts():
    c = team_fixture_counts(FX).set_index(["team", "gw"])["n"]
    assert c[(10, 2)] == 2 and c[(10, 1)] == 1


def _rows(pid, season, teams, pos="MID"):
    return pd.DataFrame({"player_id": pid, "season": season, "team_code": teams, "position": pos,
                         "gw": range(1, len(teams) + 1), "is_ghost_fixture": False,
                         "kickoff_time": [f"{season[:4]}-09-{i + 10:02d}" for i in range(len(teams))]})


def test_status_classification():
    df = pd.concat([
        _rows(1, "A", [5, 5]), _rows(1, "B", [5, 5]),          # returning
        _rows(2, "A", [5, 5]), _rows(2, "B", [5, 7, 7, 7]),    # early-season mover: majority club differs
        _rows(3, "B", [7, 7]),                                  # new
        _rows(4, "A", [5], pos="MID"), _rows(4, "B", [5], pos="FWD"),
    ])
    reg = {"A": {1: 5, 2: 5, 4: 5}, "B": {}}
    out = classify_status(df, ["A", "B"], reg).query("season == 'B'").drop_duplicates("player_id").set_index("player_id")
    assert out.loc[1, "player_status"] == "returning"
    assert out.loc[2, "player_status"] == "moved_pl_club" and out.loc[2, "mid_season_move"]
    assert out.loc[3, "player_status"] == "new_to_pl"
    assert out.loc[4, "position_changed"]
