# Phase 3 scorecard

Gate: **OPEN**  
Run: 2026-11-08T01:45:51.811441+00:00

| check | tier | value | threshold | status | note |
|---|---|---|---|---|---|
| Leakage: features for 200 player-GWs identical when all data from that GW on is removed | CRITICAL | 200/200 | 200/200 | PASS |  |
| No same-GW outcome stats in features (names + |spearman| > 0.95 with y_1 / same-GW minutes) | CRITICAL | 0 | 0 | PASS | [] max/rho/ y=0.696 min=0.768 |
| Rolling 3/5/10 (points, minutes) match hand calc for 20 players | CRITICAL | 9618/9618 values | 100% | PASS |  |
| Cold-start rows (games_played_in_PL < 3) have prior-filled features (2020-21 on) | PASS | 42338 rows, nulls={'prior_ppm': 0, 'prior_mpm': 0, 'pts_r5_blend': 0, 'mins_r5_blend': 0} | 100% non-null | PASS |  |
| games_played_in_PL monotone non-decreasing per player | PASS | 0 decreases | 0 | PASS |  |
| Rolling-5 points Spearman with next-GW points | GOOD | 0.6556 | >= 0.30 | PASS |  |
