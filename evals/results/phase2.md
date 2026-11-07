# Phase 2 scorecard

Gate: **OPEN**  
Run: 2026-11-07T22:08:58.488502+00:00

| check | tier | value | threshold | status | note |
|---|---|---|---|---|---|
| Zero duplicate (player, season, GW, fixture) keys | CRITICAL | 0 | 0 | PASS |  |
| Zero nulls in points, minutes, team, position | CRITICAL | {'total_points': 0, 'minutes': 0, 'team': 0, 'position': 0} | all 0 (-1 = column missing) | PASS |  |
| Points per GW reconcile 100% to raw | CRITICAL | 1.0 | 1.0 | PASS | raw_only=0 pg_only=0 mismatch=0 |
| role + tenure use only earlier matches (truncate-and-recompute, 200 rows) | CRITICAL | 200/200 | 200/200 | PASS |  |
| 98%+ returning players matched across seasons | PASS | 1.0 | >= 0.98 | PASS | 3443/3443 |
| role, role_season, status_detail populated with valid labels | PASS | bad_role=0 bad_role_season=0 bad_detail=0 inconsistent=0 | all 0 | PASS |  |
| 99.5%+ returning players matched across seasons | GOOD | 1.0 | >= 0.995 | PASS | 3443/3443 |
| 10 known players spot-checked (club movers, new signings, name swap, gap season) | GOOD | 10/10 | 10/10 | PASS |  |
| Mean points: starter > substitute > benchwarmer (every season) | GOOD | starter=2.76 sub=1.40 bench=0.18 | strict order all seasons | PASS |  |
