"""Feature and target column lists shared by features, models and evals."""

ROLL_STATS = ["total_points", "minutes", "expected_goals", "expected_assists", "bonus", "bps",
              "ict_index", "clean_sheets", "goals_scored", "assists", "saves", "started"]
WINDOWS = [3, 5, 10]
EWM_STATS = ["total_points", "minutes"]

ROLL_FEATURES = [f"{s}_r{w}" for s in ROLL_STATS for w in WINDOWS] + [f"{s}_ewm" for s in EWM_STATS]
HISTORY_FEATURES = ["form_trend", "mins0_share5", "start_share5", "last_minutes", "games_played_in_PL",
                    "pl_minutes_before", "prev_season_ppm", "prev_season_mpm", "gws_at_club", "apps_at_club",
                    "days_at_club"]
CONTEXT_FEATURES = ["n_fix", "is_dgw", "is_bgw", "home_share", "fdr", "opp_ga_r6", "opp_gf_r6", "opp_xga_r6",
                    "opp_xgf_r6", "opp_pts_r6", "opp_str_def", "opp_str_att", "team_gf_r6", "team_ga_r6",
                    "team_xgf_r6", "team_pts_r6", "team_str_att", "team_str_def", "fixture_uplift",
                    "high_scoring_fixture", "n_fix_next3", "fdr_next3", "n_fix_next5", "fdr_next5"]
MARKET_FEATURES = ["price", "price_change3", "selected_rank_lag1", "transfers_balance_lag1"]
COLD_FEATURES = ["prior_ppm", "prior_mpm", "prior_weight", "pts_r5_blend", "mins_r5_blend", "promoted_team"]
CATEGORICAL = ["position", "role", "status_asof"]

FEATURES = ROLL_FEATURES + HISTORY_FEATURES + CONTEXT_FEATURES + MARKET_FEATURES + COLD_FEATURES + CATEGORICAL
TARGETS = ["y_1", "y_3", "y_5"]
COLD_CORE = ["prior_ppm", "prior_mpm", "pts_r5_blend", "mins_r5_blend"]  # never null from 2020-21 on
KEY = ["player_id", "season", "gw"]
