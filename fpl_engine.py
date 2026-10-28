import requests
import pandas as pd
import pulp

from ml_pipeline import normalize_name

def fetch_current_team(team_id, gw):
    """Fetches the user's team picks and bank for a given gameweek."""
    url = f"https://fantasy.premierleague.com/api/entry/{team_id}/event/{gw}/picks/"
    response = requests.get(url)
    if response.status_code != 200:
        raise ValueError(f"Could not fetch team data (Status: {response.status_code})")
    
    data = response.json()
    picks = data['picks']
    bank = data['entry_history']['bank']
    
    return picks, bank

def fetch_bootstrap_static():
    """Fetches static player data and teams data."""
    bs = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/").json()
    
    # Process Teams
    teams = bs['teams'] # list of dicts with 'id', 'short_name', 'name'
    team_map = {t['id']: t['short_name'] for t in teams}
    
    # Process Players
    cols = ["id", "web_name", "first_name", "second_name", "element_type", "now_cost", "team", "status", "chance_of_playing_next_round"]
    players_bs = pd.DataFrame(bs["elements"])[cols]
    players_bs['full_name'] = players_bs['first_name'] + ' ' + players_bs['second_name']
    players_bs['norm_name'] = players_bs['full_name'].apply(normalize_name)
    
    # Map team short name
    players_bs['team_short_name'] = players_bs['team'].map(team_map)
    
    return players_bs, teams

def fetch_fixtures(teams):
    """
    Fetches ALL fixtures (past and future) and maps them by Team -> Event (GW).
    Returns: {team_id: {gw_id: [{'opp': 'ARS', 'home': True, 'fdr': 3, 'finished': True}, ...]}}
    """
    resp = requests.get("https://fantasy.premierleague.com/api/fixtures/")
    if resp.status_code != 200:
        return {}
        
    fixtures_data = resp.json()
    
    team_map = {t['id']: t['short_name'] for t in teams}
    # Structure: fixtures[team_id][gw] = [info, info...]
    fixtures = {} 
    
    for f in fixtures_data:
        gw = f['event']
        if gw is None: continue # unscheduled
        
        h_id = f['team_h']
        a_id = f['team_a']
        
        # Initialize team dicts if needed
        if h_id not in fixtures: fixtures[h_id] = {}
        if a_id not in fixtures: fixtures[a_id] = {}
        
        # Initialize GW list if needed
        if gw not in fixtures[h_id]: fixtures[h_id][gw] = []
        if gw not in fixtures[a_id]: fixtures[a_id][gw] = []
        
        # Home Team Info
        fixtures[h_id][gw].append({
            'opp': team_map.get(a_id, '???'),
            'home': True,
            'fdr': f['team_h_difficulty'],
            'finished': f['finished']
        })
        
        # Away Team Info
        fixtures[a_id][gw].append({
            'opp': team_map.get(h_id, '???'),
            'home': False,
            'fdr': f['team_a_difficulty'],
            'finished': f['finished']
        })
            
    return fixtures

def load_predictions_and_merge(predictions_file, players_bs):
    """Loads predictions csv and merges with bootstrap data using robust name matching."""
    df_preds = pd.read_csv(predictions_file)
    df_preds['norm_name'] = df_preds['name'].apply(normalize_name)
    
    # Map Name -> ID
    name_to_id_bs = dict(zip(players_bs['norm_name'], players_bs['id']))
    df_preds['id_live'] = df_preds['norm_name'].map(name_to_id_bs)
    
    # Fuzzy / Substring Fallback
    # Identify predictions that didn't match
    unmatched_preds = df_preds[df_preds['id_live'].isna()]
    
    if not unmatched_preds.empty:
        # Create a reverse map for manual checking (ID -> Norm Name) isn't helpful, we need to find ID for Pred Name.
        # Iterate unmatched and try to find a "good enough" match in players_bs
        # Heuristic: If 'pred_name' is inside 'live_name' or vice versa
        
        # Optimization: Pre-compute set of live names for faster lookup if list is huge (it's small ~700).
        live_names = players_bs[['id', 'norm_name']].to_dict('records')
        
        updates = {}
        for idx, row in unmatched_preds.iterrows():
            p_name = row['norm_name']
            # Try finding p_name inside live_name
            for live_p in live_names:
                l_name = live_p['norm_name']
                # Check for substring match (both directions)
                # Ensure it's not a tiny substring (e.g. 'ed' matching 'ederson')
                if len(p_name) > 4 and (p_name in l_name or l_name in p_name):
                    updates[idx] = live_p['id']
                    break # Take first match
        
        # Apply updates
        if updates:
            print(f"Fuzzy matched {len(updates)} players (e.g. '{df_preds.loc[list(updates.keys())[0], 'name']}')")
            df_preds.loc[updates.keys(), 'id_live'] = list(updates.values())
    
    # Merge
    df_merged = df_preds.dropna(subset=['id_live']).copy()
    df_merged['id'] = df_merged['id_live'].astype(int)
    
    # Attach live data (costs, types, status)
    # Also drop 'position' from predictions if it exists to avoid confusion
    if 'position' in df_merged.columns:
        df_merged = df_merged.drop(columns=['position'])
    
    df_merged = df_merged.merge(players_bs[['id', 'now_cost', 'element_type', 'status', 'chance_of_playing_next_round', 'team_short_name', 'team']], on='id', how='inner')
    
    # Consolidate 'team' column to be the numeric ID from BS
    if 'team_y' in df_merged.columns:
        df_merged['team'] = df_merged['team_y']
        df_merged = df_merged.drop(columns=['team_y'])
        # team_x is the CSV string name, we can keep it or rename it
        df_merged = df_merged.rename(columns={'team_x': 'team_csv_name'})
    
    # --- BASELINE INJECTION FOR NEW SIGNINGS ---
    # Identify fit players in live API who are NOT in our predictions
    matched_ids = set(df_merged['id'])
    
    # Filter for fit players in the live API
    fit_players_bs = players_bs[
        (players_bs['status'] == 'a') | 
        (players_bs['chance_of_playing_next_round'] == 100)
    ].copy()
    
    missing_fit_players = fit_players_bs[~fit_players_bs['id'].isin(matched_ids)].copy()
    
    if not missing_fit_players.empty:
        # Create baseline records
        baseline_df = pd.DataFrame({
            'name': missing_fit_players['web_name'],
            'predicted_points': 2.0, # Baseline estimate for a starting player
            'value': missing_fit_players['now_cost'],
            'team': missing_fit_players['team'],
            'team_csv_name': missing_fit_players['team_short_name'], # Placeholder
            'id': missing_fit_players['id'],
            'now_cost': missing_fit_players['now_cost'],
            'element_type': missing_fit_players['element_type'],
            'status': missing_fit_players['status'],
            'chance_of_playing_next_round': missing_fit_players['chance_of_playing_next_round'],
            'team_short_name': missing_fit_players['team_short_name']
        })
        df_merged = pd.concat([df_merged, baseline_df], ignore_index=True)
        print(f"Injected {len(baseline_df)} fit players with baseline predictions (e.g. '{baseline_df.iloc[0]['name']}')")
    
    # Standardize position column based on LIVE API
    type_to_pos = {1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD'}
    df_merged['position'] = df_merged['element_type'].map(type_to_pos)

    # Final filter to ensure df_merged only contains fit players (prediction + baseline)
    df_merged = df_merged[
        (df_merged['status'] == 'a') | 
        (df_merged['chance_of_playing_next_round'] == 100)
    ].copy()

    # Resolve Team column - now it is always 'team' (int)
    team_col = 'team'
    
    return df_merged, team_col

def optimize_transfers(current_team_ids, bank, df_merged, team_col, transfer_limit=1, players_bs=None, next_fixture_map=None):
    """
    Runs the linear programming optimizer.
    Returns:
        - status (str)
        - sold_players (list of dicts)
        - bought_players (list of dicts)
        - final_team_df (DataFrame)
        - total_points (float)
        - missing_players (list of names)
    """
    
    # 1. Costs & Budget
    # Use full bootstrap data to find selling prices for ALL current players
    name_map_bs = {}
    pos_map_bs = {}
    status_map_bs = {}
    chance_map_bs = {}
    team_name_map_bs = {}
    team_id_map_bs = {}
    
    if players_bs is not None:
        cost_lookup_bs = dict(zip(players_bs['id'], players_bs['now_cost']))
        name_map_bs = dict(zip(players_bs['id'], players_bs['web_name']))
        pos_map_bs = dict(zip(players_bs['id'], players_bs['element_type']))
        status_map_bs = dict(zip(players_bs['id'], players_bs['status']))
        chance_map_bs = dict(zip(players_bs['id'], players_bs['chance_of_playing_next_round']))
        team_name_map_bs = dict(zip(players_bs['id'], players_bs['team_short_name']))
        team_id_map_bs = dict(zip(players_bs['id'], players_bs['team']))
        current_team_value_total = sum(cost_lookup_bs.get(pid, 0) for pid in current_team_ids)
    else:
        # Fallback if BS not provided
        cost_lookup = dict(zip(df_merged['id'], df_merged['now_cost']))
        current_team_value_total = sum(cost_lookup.get(pid, 0) for pid in current_team_ids if pid in cost_lookup)
    
    # Total budget available for the 15 players we will pick
    total_budget = bank + current_team_value_total
    
    # Maps
    players_ids = df_merged['id'].tolist()
    points_map = dict(zip(df_merged['id'], df_merged['predicted_points']))
    opt_cost_map = dict(zip(df_merged['id'], df_merged['now_cost']))
    position_map = dict(zip(df_merged['id'], df_merged['position']))
    
    # Determine valid current players (those in current team AND prediction set)
    valid_current_team_ids = [pid for pid in current_team_ids if pid in players_ids]
    
    # Identify players in current team MISSING from model or UNFIT
    # 1. Check if they are in the selectable fit pool (df_merged)
    # 2. If not, check if they are in the live API (players_bs) to see WHY
    missing_players = []
    missing_player_ids = [pid for pid in current_team_ids if pid not in players_ids]
    
    for pid in missing_player_ids:
        name = name_map_bs.get(pid, f"ID:{pid}")
        status = status_map_bs.get(pid, 'u')
        chance = chance_map_bs.get(pid)
        
        if status != 'a' and (chance is not None and chance < 100):
            missing_players.append(f"{name} (Injured/Doubtful)")
        else:
            missing_players.append(f"{name} (Missing Model Data)")

    # ---------------------------------------------------------
    # Solver Loop (Relaxing Transfer Count until feasible)
    # ---------------------------------------------------------
    forced_sales_count = len(missing_player_ids)
    limit_to_try = max(transfer_limit, forced_sales_count)
    
    status_code = "Infeasible"
    prob = None
    selection = None
    
    # Try increasing the transfer limit if initial attempt fails
    # This handles cases where we MUST sell others to stay under budget/team limits
    while limit_to_try <= 15:
        prob = pulp.LpProblem(f"FPL_Optimizer_L{limit_to_try}", pulp.LpMaximize)
        selection = pulp.LpVariable.dicts("player", players_ids, 0, 1, pulp.LpBinary)
        
        # Obj
        prob += pulp.lpSum([points_map[i] * selection[i] for i in players_ids]), "Total Points"
        
        # Constraints
        prob += pulp.lpSum([selection[i] for i in players_ids]) == 15, "Squad Size"
        prob += pulp.lpSum([opt_cost_map[i] * selection[i] for i in players_ids]) <= total_budget, "Budget"
        
        # Positions
        prob += pulp.lpSum([selection[i] for i in players_ids if position_map[i] == 'GK']) == 2, "GK Limit"
        prob += pulp.lpSum([selection[i] for i in players_ids if position_map[i] == 'DEF']) == 5, "DEF Limit"
        prob += pulp.lpSum([selection[i] for i in players_ids if position_map[i] == 'MID']) == 5, "MID Limit"
        prob += pulp.lpSum([selection[i] for i in players_ids if position_map[i] == 'FWD']) == 3, "FWD Limit"
        
        # Teams
        unique_teams = df_merged[team_col].unique()
        for team in unique_teams:
            team_ids = df_merged[df_merged[team_col] == team]['id'].tolist()
            prob += pulp.lpSum([selection[i] for i in team_ids]) <= 3, f"Max 3 {team}"
            
        # Transfer Limit (Adaptive)
        prob += pulp.lpSum([selection[i] for i in valid_current_team_ids]) >= (15 - limit_to_try), "Transfer Limit"
        
        # Solve
        prob.solve(pulp.PULP_CBC_CMD(msg=0))
        
        if pulp.LpStatus[prob.status] == 'Optimal':
            status_code = "Optimal"
            break
        
        limit_to_try += 1 # Relax and try again
    
    if status_code != 'Optimal':
        return "Infeasible", [], [], pd.DataFrame(), 0.0, missing_players, []
        
    # Results extraction
    selected_ids = [i for i in players_ids if pulp.value(selection[i]) == 1]
    
    # Identify which fit players in the team used baseline predictions
    baseline_players = [
        name_map_bs.get(pid) for pid in current_team_ids 
        if pid in players_ids and points_map.get(pid) == 2.0
    ]
    
    sold_valid = [pid for pid in valid_current_team_ids if pid not in selected_ids]
    # IMPORTANT: Include missing players (injured/unpredicted) who are also effectively sold
    all_sold_ids = sold_valid + missing_player_ids
    
    bought_ids = [pid for pid in selected_ids if pid not in valid_current_team_ids]
    
    # Build transfer lists with names and positions
    type_to_pos = {1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD'}
    pos_priority = {'GK': 1, 'DEF': 2, 'MID': 3, 'FWD': 4}
    
    sold_list = []
    for pid in all_sold_ids:
        pos_id = pos_map_bs.get(pid)
        pos_str = type_to_pos.get(pos_id, "???")
        
        # Get Team & Fixture Info
        team_short = team_name_map_bs.get(pid, "UNKNOWN")
        team_id = team_id_map_bs.get(pid)
        fix_info = next_fixture_map.get(team_id, {}) if next_fixture_map else {}
        
        sold_list.append({
            'name': name_map_bs.get(pid, f"ID:{pid}"),
            'id': pid,
            'points': points_map.get(pid, 0.0),
            'cost': opt_cost_map.get(pid, cost_lookup_bs.get(pid, 0)) if players_bs is not None else 0,
            'pos': pos_str,
            'prio': pos_priority.get(pos_str, 5),
            'team': team_short,
            'fix': fix_info
        })
    sold_list.sort(key=lambda x: x['prio'])
        
    bought_list = []
    # Create maps for purchased players using df_merged
    bought_team_map = dict(zip(df_merged['id'], df_merged['team_short_name']))
    bought_team_id_map = dict(zip(df_merged['id'], df_merged['team'])) # team ID from df_merged
    
    for pid in bought_ids:
        pos_str = position_map.get(pid) # from df_merged
        
        team_short = bought_team_map.get(pid, "UNKNOWN")
        team_id = bought_team_id_map.get(pid)
        fix_info = next_fixture_map.get(team_id, {}) if next_fixture_map else {}
        
        bought_list.append({
            'name': name_map_bs.get(pid, f"ID:{pid}"),
            'id': pid,
            'points': points_map.get(pid, 0.0),
            'cost': opt_cost_map.get(pid, 0),
            'pos': pos_str,
            'prio': pos_priority.get(pos_str, 5),
            'team': team_short,
            'fix': fix_info
        })
    bought_list.sort(key=lambda x: x['prio'])
    
    final_df = df_merged[df_merged['id'].isin(selected_ids)].sort_values(['position', 'predicted_points'], ascending=[True, False])
    
    return "Optimal", sold_list, bought_list, final_df, pulp.value(prob.objective), missing_players, baseline_players

def get_top_n_transfers(current_team_ids, bank, df_merged, players_bs, n=3, next_fixture_map=None, missing_player_ids=None):
    """
    Evaluates transfers, prioritizing replacements for missing/injured players.
    """
    if players_bs is None or df_merged.empty:
        return []
        
    if missing_player_ids is None:
        missing_player_ids = []

    # Prepare maps
    team_col = 'team_x' if 'team_x' in df_merged.columns else 'team'
    
    cost_lookup = dict(zip(players_bs['id'], players_bs['now_cost']))
    points_map = dict(zip(df_merged['id'], df_merged['predicted_points']))
    pos_map = dict(zip(players_bs['id'], players_bs['element_type'])) # element_type: 1-4
    
    # Map element_type to prediction string positions for matching
    type_to_pos = {1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD'}
    bs_name_map = dict(zip(players_bs['id'], players_bs['web_name']))
    bs_team_name_map = dict(zip(players_bs['id'], players_bs['team_short_name']))
    bs_team_id_map = dict(zip(players_bs['id'], players_bs['team']))
    
    # Current Team counts for Team Limit
    team_counts = players_bs[players_bs['id'].isin(current_team_ids)]['team'].value_counts().to_dict()
    
    # Helper to evaluate moves
    def evaluate_moves(sellers_list, limit_count=3):
        options = []
        for sell_id in sellers_list:
            sell_name = bs_name_map.get(sell_id, f"ID:{sell_id}")
            sell_price = cost_lookup.get(sell_id, 0)
            sell_pts = points_map.get(sell_id, 0.0)
            sell_type = pos_map.get(sell_id) # 1-4
            sell_team_id = bs_team_id_map.get(sell_id)
            sell_team_short = bs_team_name_map.get(sell_id, "UNK")
            
            # Buy Candidates
            buy_candidates = df_merged[
                (df_merged['element_type'] == sell_type) & 
                (~df_merged['id'].isin(current_team_ids))
            ]
            
            # Optimization: Pre-filter buy candidates slightly to avoid massive loops?
            # Or just iterate. df_merged isn't huge (600 rows).
            
            for _, buy_row in buy_candidates.iterrows():
                buy_id = int(buy_row['id'])
                buy_price = buy_row['now_cost']
                buy_pts = buy_row['predicted_points']
                buy_team_id = buy_row['team']
                buy_team_short = buy_row['team_short_name']
                
                # Check Budget
                if buy_price <= (bank + sell_price):
                    # Check Team Limit
                    current_count = team_counts.get(buy_team_id, 0)
                    if sell_team_id == buy_team_id:
                        new_count = current_count 
                    else:
                        new_count = current_count + 1
                    
                    if new_count <= 3:
                        gain = buy_pts - sell_pts
                        # RELAXED CONSTRAINT: Allow any valid move, sort by gain later.
                        # Only filter wildly negative moves to keep quality high?
                        # Let's keep all, but maybe limit distinct 'sell' options if too many.
                        
                        buy_fix = next_fixture_map.get(buy_team_id, []) if next_fixture_map else []
                        sell_fix = next_fixture_map.get(sell_team_id, []) if next_fixture_map else []
                        
                        options.append({
                            'gain': gain,
                            'sell': {
                                'name': sell_name, 'pts': sell_pts, 'price': sell_price, 
                                'team': sell_team_short, 'fix': sell_fix
                            },
                            'buy': {
                                'name': buy_row['name'], 'pts': buy_pts, 'price': buy_price,
                                'team': buy_team_short, 'fix': buy_fix
                            },
                            'type': 'urgent' if sell_id in missing_player_ids else 'value'
                        })
        
        # Sort by gain descending
        options.sort(key=lambda x: x['gain'], reverse=True)
        # Return top N
        return options[:limit_count]
        
    final_suggestions = []
    seen_suggestions = set() # Track "Sell X -> Buy Y" to avoid dupes
    
    # 1. PRIORITY: Fix Missing/Injured Players
    if missing_player_ids:
        for pid in missing_player_ids:
             # Get top move for this specific player
             moves = evaluate_moves([pid], limit_count=1)
             if moves:
                 best_move = moves[0]
                 best_move['note'] = "🚑 Priority Fix"
                 final_suggestions.append(best_move)
                 seen_suggestions.add((best_move['sell']['name'], best_move['buy']['name']))
                 
    # 2. FILLER: Best Value Upgrades
    slots_remaining = n - len(final_suggestions)
    if slots_remaining > 0:
        # Evaluate ALL moves (including selling healthy players)
        # We ask for more initially (limit_count=50) to filter dupes
        all_moves = evaluate_moves(current_team_ids, limit_count=50)
        
        for move in all_moves:
            sig = (move['sell']['name'], move['buy']['name'])
            if sig not in seen_suggestions:
                move['note'] = "💎 Value Upgrade"
                final_suggestions.append(move)
                seen_suggestions.add(sig)
                
                if len(final_suggestions) >= n:
                    break
                    
    return final_suggestions
