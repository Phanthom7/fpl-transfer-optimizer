# Phase 2 scorecard

Gate: **OPEN**  
Run: 2026-11-07T21:46:05.969637+00:00

| check | tier | value | threshold | status | note |
|---|---|---|---|---|---|
| Zero duplicate (player, season, GW, fixture) keys | CRITICAL | 0 | 0 | PASS |  |
| Zero nulls in points, minutes, team, position | CRITICAL | {'total_points': 0, 'minutes': 0, 'team': 0, 'position': 0} | all 0 (-1 = column missing) | PASS |  |
| Points per GW reconcile 100% to raw | CRITICAL | 1.0 | 1.0 | PASS | raw_only=0 pg_only=0 mismatch=0 |
| 98%+ returning players matched across seasons | PASS | 1.0 | >= 0.98 | PASS | 3443/3443 |
| 99.5%+ returning players matched across seasons | GOOD | 1.0 | >= 0.995 | PASS | 3443/3443 |
| 10 known players spot-checked (club movers, new signings, name swap, gap season) | GOOD | 10/10 | 10/10 | PASS |  |
