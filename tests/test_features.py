import numpy as np
import pandas as pd

from src.features import build as fb


def test_tkey_orders_across_seasons():
    t = fb.tkey(pd.Series(["2020-21", "2020-21", "2021-22"]), pd.Series([38, 1, 1]))
    assert t[1] < t[0] < t[2]


def test_asof_before_is_strict():
    left = pd.DataFrame({"p": [1, 1, 1], "t": [1, 2, 3]})
    right = pd.DataFrame({"p": [1, 1], "t": [1, 2], "v": [10.0, 20.0]})
    out = fb.asof_before(left, right, "p", ["v"])
    assert np.isnan(out["v"][0]) and out["v"][1] == 10.0 and out["v"][2] == 20.0


def test_targets_forward_sums_and_unfinished_is_nan():
    g = pd.DataFrame({"player_id": 1, "season": "2020-21", "gw": [1, 2, 3, 4, 5],
                      "total_points": [1, 2, 3, 4, 5], "finished": [True, True, True, True, False]})
    out = fb.targets(g)
    assert out["y_1"].tolist()[:4] == [1, 2, 3, 4] and np.isnan(out["y_1"][4])
    assert out["y_3"].tolist()[:2] == [6, 9] and np.isnan(out["y_3"][2])
    assert np.isnan(out["y_5"][0])


def test_team_schedule_ahead_counts_dgw_and_blank():
    sch = pd.DataFrame({"season": "2020-21", "gw": [1, 2, 2, 4], "fixture": [1, 2, 3, 4],
                        "home_code": [10, 10, 20, 10], "away_code": [20, 30, 10, 30],
                        "fdr_h": [2, 3, 4, 5], "fdr_a": [3, 2, 2, 2]})
    a = fb.team_schedule_ahead(sch).set_index(["team_code", "gw"])
    assert a.loc[(10, 1), "n_fix_next3"] == 3      # gw1:1 + gw2:2 (DGW) + gw3:0 (blank)
    assert a.loc[(10, 3), "n_fix_next3"] == 1      # gw3 blank, gw4 1, gw5 0
