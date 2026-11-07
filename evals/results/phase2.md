# Phase 2 scorecard

Gate: **BLOCKED**  
Run: 2026-11-07T21:34:46.527783+00:00

| check | tier | value | threshold | status | note |
|---|---|---|---|---|---|
| Zero duplicate (player, season, GW, fixture) keys | CRITICAL | None | None | FAIL | tests/evals/test_phase2_clean.py:20: AssertionError |
| Zero nulls in points, minutes, team, position | CRITICAL | None | None | FAIL | tests/evals/test_phase2_clean.py:20: AssertionError |
| Points per GW reconcile 100% to raw | CRITICAL | None | None | FAIL | tests/evals/test_phase2_clean.py:20: AssertionError |
| 98%+ returning players matched across seasons | PASS | None | None | FAIL | tests/evals/test_phase2_clean.py:20: AssertionError |
| 99.5%+ returning players matched across seasons | GOOD | None | None | FAIL | tests/evals/test_phase2_clean.py:20: AssertionError |
| 10 known players spot-checked (club movers, new signings, name swap, gap season) | GOOD | None | None | FAIL | tests/evals/test_phase2_clean.py:20: AssertionError |
