from __future__ import annotations

from pathlib import Path

import streamlit as st

import fpl_engine

DEFAULT_PREDICTIONS_FILE = Path("artifacts/predictions.csv")

st.set_page_config(page_title="FPL Transfer Optimizer", layout="wide")

st.title("⚽️ FPL Transfer Optimizer")
st.markdown("Enter your Team ID to get AI-powered transfer suggestions under FPL squad constraints.")

st.sidebar.header("Configuration")
team_id = st.sidebar.text_input("FPL Team ID", value="1364541")
gw = st.sidebar.number_input("Gameweek", value=24, step=1)


def render_player(player, sub=False, fixture_info=None):
    name = player.get("web_name", f"ID: {player['element']}")
    cost = player.get("now_cost", 0) / 10
    color = "#9e9e9e" if sub else "#00c853"
    team_name = player.get("team_short_name", "UNK")

    fix_badges_html = ""
    if fixture_info:
        if not isinstance(fixture_info, list):
            fixture_info = [fixture_info]

        for fix in fixture_info:
            opp = fix.get("opp", "-")
            home = fix.get("home", True)
            fdr = fix.get("fdr", 3)
            finished = fix.get("finished", False)

            fdr_colors = {
                1: "#00796B",
                2: "#00c853",
                3: "#e0e0e0",
                4: "#ff1744",
                5: "#b71c1c",
            }
            bg_color = fdr_colors.get(fdr, "#e0e0e0")
            text_color = "black" if fdr in [2, 3] else "white"
            loc = "(H)" if home else "(A)"
            opacity = "0.5" if finished else "1.0"
            fix_badges_html += (
                f'<div style="background-color: {bg_color}; color: {text_color}; '
                f'font-size: 0.65em; padding: 2px 5px; border-radius: 4px; margin-top: 2px; '
                f'display: inline-block; font-weight: bold; opacity: {opacity}; margin-right: 2px;">'
                f"vs {opp} {loc}</div>"
            )

    st.markdown(
        f"""
        <div style="background-color: #f0f2f6; color: #1a1c24; border-left: 5px solid {color}; padding: 8px; margin: 5px; border-radius: 6px; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <strong style="color: #1a1c24; font-size: 0.95em;">{name}</strong><br>
            <div style="font-size: 0.75em; color: #555; margin-bottom: 2px;">{team_name}</div>
            <div style="font-size: 0.85em; color: #333; font-weight: 500;">£{cost}m</div>
            <div style="display: flex; flex-wrap: wrap; justify-content: center; margin-top: 4px;">{fix_badges_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def display_pitch(picks, players_bs, fixtures_map, gw):
    player_map = players_bs.set_index("id").to_dict("index")
    starters = []
    subs = []

    for pick in picks:
        pid = pick["element"]
        player_data = player_map.get(pid, {})
        combined = {**pick, **player_data}
        if pick["position"] <= 11:
            starters.append(combined)
        else:
            subs.append(combined)

    gk = [player for player in starters if player.get("element_type") == 1]
    defs = [player for player in starters if player.get("element_type") == 2]
    mids = [player for player in starters if player.get("element_type") == 3]
    fwds = [player for player in starters if player.get("element_type") == 4]

    st.subheader(f"Current Team ({len(defs)}-{len(mids)}-{len(fwds)})")
    c1, c2 = st.columns([3, 1])

    def get_fix(player_data):
        team_value = player_data.get("team")
        if team_value:
            return fixtures_map.get(team_value, {}).get(gw, [])
        return []

    with c1:
        st.markdown("### Starting XI")
        cols_gk = st.columns(len(gk) + 2)
        if gk:
            with cols_gk[1]:
                render_player(gk[0], fixture_info=get_fix(gk[0]))

        cols_def = st.columns(len(defs))
        for i, player in enumerate(defs):
            with cols_def[i]:
                render_player(player, fixture_info=get_fix(player))

        cols_mid = st.columns(len(mids))
        for i, player in enumerate(mids):
            with cols_mid[i]:
                render_player(player, fixture_info=get_fix(player))

        cols_fwd = st.columns(len(fwds))
        for i, player in enumerate(fwds):
            with cols_fwd[i]:
                render_player(player, fixture_info=get_fix(player))

    with c2:
        st.markdown("### Bench")
        for player in subs:
            render_player(player, sub=True, fixture_info=get_fix(player))


def load_predictions_file():
    if not DEFAULT_PREDICTIONS_FILE.exists():
        st.error(
            f"Predictions file not found at `{DEFAULT_PREDICTIONS_FILE}`. Run `python feature_engineering.py`, "
            "`python train_model.py`, and `python generate_predictions.py` first."
        )
        st.stop()
    return str(DEFAULT_PREDICTIONS_FILE)


if st.sidebar.button("Analyze & Optimize Team", type="primary"):
    with st.spinner("Fetching data and optimizing..."):
        try:
            picks, bank = fpl_engine.fetch_current_team(team_id, gw)
            players_bs, teams = fpl_engine.fetch_bootstrap_static()
            all_fixtures = fpl_engine.fetch_fixtures(teams)
            display_pitch(picks, players_bs, all_fixtures, gw)

            st.subheader("📊 Team Summary")
            col1, col2, col3 = st.columns(3)

            cost_map = players_bs.set_index("id")["now_cost"].to_dict()
            squad_value = sum(cost_map.get(player["element"], 0) for player in picks) / 10

            col1.metric("Current Squad Value", f"£{squad_value:.1f}m")
            col2.metric("Bank Balance", f"£{bank / 10:.1f}m")

            predictions_file = load_predictions_file()
            df_merged, team_col = fpl_engine.load_predictions_and_merge(predictions_file, players_bs)

            next_fixture_map = {}
            for team in teams:
                team_id_value = team["id"]
                team_fixtures = all_fixtures.get(team_id_value, {})
                for gameweek in sorted(team_fixtures.keys()):
                    gw_fixtures = team_fixtures[gameweek]
                    if any(not fixture["finished"] for fixture in gw_fixtures):
                        next_fixture_map[team_id_value] = gw_fixtures
                        break

            status, sold, bought, final_df, total_points, missing_players, baseline_players = fpl_engine.optimize_transfers(
                [player["element"] for player in picks],
                bank,
                df_merged,
                team_col,
                transfer_limit=1,
                players_bs=players_bs,
                next_fixture_map=next_fixture_map,
            )

            missing_ids = []
            if missing_players:
                for missing_player in missing_players:
                    name_part = missing_player.split(" (")[0]
                    found = players_bs[players_bs["web_name"] == name_part]
                    if not found.empty:
                        missing_ids.append(found.iloc[0]["id"])

            st.markdown(
                """
                <style>
                @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');

                html, body, [class*="css"] {
                    font-family: 'Outfit', sans-serif;
                }

                .fpl-card {
                    background: rgba(255, 255, 255, 0.05);
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                    padding: 12px;
                    margin-bottom: 10px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
                    transition: transform 0.2s;
                }

                .fpl-card:hover {
                    border-color: rgba(255, 255, 255, 0.2);
                    transform: translateY(-2px);
                    box-shadow: 0 8px 12px rgba(0, 0, 0, 0.1);
                }

                .sell-badge {
                    background: linear-gradient(135deg, #ff4b4b, #d32f2f);
                    color: white !important;
                    padding: 3px 10px;
                    border-radius: 99px;
                    font-size: 0.65em;
                    font-weight: 800;
                    letter-spacing: 0.5px;
                    display: inline-block;
                    margin-bottom: 4px;
                    box-shadow: 0 2px 4px rgba(211, 47, 47, 0.3);
                }
                .buy-badge {
                    background: linear-gradient(135deg, #00c853, #009624);
                    color: white !important;
                    padding: 3px 10px;
                    border-radius: 99px;
                    font-size: 0.65em;
                    font-weight: 800;
                    letter-spacing: 0.5px;
                    display: inline-block;
                    margin-bottom: 4px;
                    box-shadow: 0 2px 4px rgba(0, 150, 36, 0.3);
                }
                </style>
                """,
                unsafe_allow_html=True,
            )

            if missing_players:
                st.warning("⚠️ The following players are flagging as unavailable (injured/suspended) and will be replaced:")
                for player in missing_players:
                    st.write(f"- {player}")

            if baseline_players:
                st.info("ℹ️ Some players were not in our predictive model but are healthy. We used a baseline estimate (2.0 pts) to decide if you should keep them:")
                for player in baseline_players:
                    st.write(f"- {player}")

            if status != "Optimal":
                st.error("Could not find an optimal solution. Try relaxing constraints or checking valid players.")
            else:
                col3.metric("New Projected Score", f"{total_points:.1f}")

                def get_fix_html(fix_list):
                    if not fix_list:
                        return ""
                    if not isinstance(fix_list, list):
                        fix_list = [fix_list]

                    html = ""
                    for fix in fix_list:
                        fdr_colors = {
                            1: "#00796B",
                            2: "#00c853",
                            3: "#e0e0e0",
                            4: "#ff1744",
                            5: "#b71c1c",
                        }
                        fdr = fix.get("fdr", 3)
                        finished = fix.get("finished", False)
                        bg = fdr_colors.get(fdr, "#e0e0e0")
                        fg = "black" if fdr in [2, 3] else "white"
                        loc = "(H)" if fix.get("home") else "(A)"
                        opacity = "0.5" if finished else "1.0"
                        html += (
                            f'<div style="background-color: {bg}; color: {fg}; font-size: 0.65em; '
                            f'padding: 2px 5px; border-radius: 4px; margin-top: 2px; display: inline-block; '
                            f'font-weight: bold; opacity: {opacity}; margin-right: 2px;">'
                            f"vs {fix.get('opp')} {loc}</div>"
                        )
                    return html

                st.markdown("---")
                st.subheader("🔥 Recommended Moves")
                top_options = fpl_engine.get_top_n_transfers(
                    [player["element"] for player in picks],
                    bank,
                    df_merged,
                    players_bs,
                    n=5,
                    next_fixture_map=next_fixture_map,
                    missing_player_ids=missing_ids,
                )

                if not top_options:
                    st.info("No transfers found within constraints.")
                else:
                    for option in top_options:
                        gain_color = "#00c853" if option["gain"] > 0 else "#e0e0e0"
                        diff = option["sell"]["price"] - option["buy"]["price"]
                        cost_label = "Bank Gain" if diff >= 0 else "Cost"
                        cost_value = abs(diff) / 10
                        cost_color = "#66bb6a" if diff >= 0 else "#ef5350"

                        st.markdown(
                            f"""
<div class="fpl-card" style="padding: 10px; border: 1px solid rgba(255,255,255,0.05);">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
        <div style="font-size: 0.8em; font-weight: 700; color: #888; text-transform: uppercase;">{option.get("note", "Option")}</div>
        <div style="font-size: 0.9em; font-weight: 700; color: {gain_color};">+{option["gain"]:.1f} pts</div>
    </div>
    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div style="flex: 1; text-align: left;">
            <div class="sell-badge">SELL</div>
            <div style="font-size: 1.0em; font-weight: 700; line-height: 1.2;">{option["sell"]["name"]}</div>
            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px; margin-top: 2px;">
                <div style="font-size: 0.75em; opacity: 0.7;">{option["sell"].get("team", "UNK")} | £{option["sell"]["price"]/10:.1f}m</div>
                {get_fix_html(option["sell"].get("fix"))}
            </div>
        </div>
        <div style="flex: 0; padding: 10px 10px 0 10px; opacity: 0.3; font-size: 1.2em;">➔</div>
        <div style="flex: 1; text-align: right;">
            <div class="buy-badge">BUY</div>
            <div style="font-size: 1.0em; font-weight: 700; line-height: 1.2;">{option["buy"]["name"]}</div>
            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px; margin-top: 2px; justify-content: flex-end;">
                <div style="font-size: 0.75em; opacity: 0.7;">{option["buy"].get("team", "UNK")} | £{option["buy"]["price"]/10:.1f}m</div>
                {get_fix_html(option["buy"].get("fix"))}
            </div>
        </div>
    </div>
    <div style="margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(255,255,255,0.05); text-align: right; font-size: 0.75em;">
        <span style="opacity: 0.6;">{cost_label}: </span>
        <strong style="color: {cost_color};">£{cost_value:.1f}m</strong>
    </div>
</div>
                            """,
                            unsafe_allow_html=True,
                        )

        except Exception as exc:
            st.error(f"An error occurred: {exc}")
            import traceback

            st.code(traceback.format_exc())
