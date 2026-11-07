import pandas as pd
import numpy as np

# Load the cleaned data
df = pd.read_csv('/Users/Vishnu/Desktop/Python/AI/FPL/fpl_cleaned.csv')

# Define metric groups
team_metrics = ['attack_score', 'defence_score', 'team_strength']
opp_metrics = ['opp_attack_score', 'opp_defence_score', 'opp_team_strength']
player_metrics = ['rolling_avg_3', 'rolling_avg_5']
difficulty_metrics = ['fixture_difficulty_attack', 'fixture_difficulty_defence', 'fixture_difficulty_overall']

# 1. Fill Team Metrics (Median per team per season)
for col in team_metrics:
    if col in df.columns:
        df[col] = df.groupby(['team', 'season_x'])[col].transform(lambda x: x.fillna(x.median()))
        # Fallback to global median for that column
        df[col] = df[col].fillna(df[col].median())

# 2. Fill Opponent Metrics (Median per opponent per season)
for col in opp_metrics:
    if col in df.columns:
        df[col] = df.groupby(['opp_team_name', 'season_x'])[col].transform(lambda x: x.fillna(x.median()))
        # Fallback to global median
        df[col] = df[col].fillna(df[col].median())

# 3. Fill Player Metrics (Median per player per season)
# Note: If these columns aren't in the CSV yet (added in notebook but not saved), we'll handle that
if all(col in df.columns for col in player_metrics):
    for col in player_metrics:
        df[col] = df.groupby(['name', 'season_x'])[col].transform(lambda x: x.fillna(x.median()))
        # Fallback to 0 for players with NO history at all
        df[col] = df[col].fillna(0)

# 4. Fill Difficulty Metrics (Median per team/opp combination or global)
for col in difficulty_metrics:
    if col in df.columns:
        df[col] = df[col].fillna(df[col].median())

# Final check for any remaining NaNs
remaining_nulls = df.isnull().sum()
print("\nRemaining nulls per column:")
print(remaining_nulls[remaining_nulls > 0])

# Drop any remaining rows with NaNs in critical columns if they exist
df = df.dropna()

# Save the final cleaned and filled datasetdf.to_csv('fpl_cleaned_ml.csv', index=False)
print(f"\nData filled and saved to fpl_cleaned_ml.csv. Total rows: {len(df)}")
