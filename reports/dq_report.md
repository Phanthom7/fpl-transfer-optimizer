# Data quality report: player_gw

- rows: 191,844
- ghost rows (postponed placeholders, kept + flagged): 59
- duplicate (player, season, gw, fixture) keys: 0
- positions: {'MID': 82108, 'DEF': 64501, 'FWD': 23534, 'GK': 21379, 'AM': 322}
- columns with nulls: {'starts': 72372, 'expected_goals': 72372, 'expected_assists': 72372, 'expected_goal_involvements': 72372, 'expected_goals_conceded': 72372, 'defensive_contribution': 156207, 'clearances_blocks_interceptions': 156207, 'recoveries': 156207, 'tackles': 156207, 'xP': 28450, 'team_h_score': 59, 'team_a_score': 59, 'starts_last5': 59, 'apps_last5': 59, 'gws_at_club': 59, 'apps_at_club': 59, 'days_at_club': 59}

## Per season (ghost rows excluded)

| season   |   rows |   players |   gws |   dgw_rows |   minutes_gt0 |   moved_pl_club |   new_fringe |   new_promoted_club |   new_signing |   returned_to_pl |   returning |   season_benchwarmer |   season_starter |   season_substitute |   mid_season_move |   position_changed |   promoted_teams |
|:---------|-------:|----------:|------:|-----------:|--------------:|----------------:|-------------:|--------------------:|--------------:|-----------------:|------------:|---------------------:|-----------------:|--------------------:|------------------:|-------------------:|-----------------:|
| 2019-20  |  22501 |       666 |    38 |        376 |         10614 |              31 |           79 |                  89 |            68 |                0 |         399 |                  254 |              213 |                 199 |                 7 |                  0 |                3 |
| 2020-21  |  24365 |       713 |    38 |       2913 |         10393 |              44 |           88 |                  80 |            64 |               26 |         411 |                  303 |              215 |                 195 |                13 |                 20 |                3 |
| 2021-22  |  25447 |       737 |    38 |       4434 |         10485 |              43 |           90 |                  83 |            51 |               47 |         423 |                  339 |              218 |                 180 |                14 |                  9 |                3 |
| 2022-23  |  26505 |       778 |    37 |       3096 |         11345 |              57 |          112 |                  77 |            80 |               42 |         410 |                  335 |              226 |                 217 |                27 |                 14 |                3 |
| 2023-24  |  29725 |       865 |    38 |       1966 |         11384 |              56 |          131 |                  96 |            59 |               53 |         470 |                  421 |              218 |                 226 |                23 |                 12 |                3 |
| 2024-25  |  27605 |       804 |    38 |        748 |         11566 |              67 |          114 |                  60 |            64 |               53 |         446 |                  366 |              232 |                 206 |                29 |                  9 |                3 |
| 2025-26  |  29747 |       841 |    38 |        818 |         11492 |              67 |          100 |                  83 |            74 |               50 |         467 |                  421 |              226 |                 194 |                27 |                 12 |                3 |
| 2026-27  |   5890 |       670 |     9 |          0 |          2771 |              65 |           17 |                  69 |            61 |               41 |         417 |                  276 |              222 |                 172 |                17 |                 11 |                3 |
