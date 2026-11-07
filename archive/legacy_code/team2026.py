import requests
import pandas as pd

TEAM_ID = 1364541   # <- your entry id
GW = 24             # <- gameweek you want

url = f"https://fantasy.premierleague.com/api/entry/{TEAM_ID}/event/{GW}/picks/"
data = requests.get(url).json()

picks_df = pd.DataFrame(data["picks"])
print(picks_df.head())

bs = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/").json()

players = pd.DataFrame(bs["elements"])[["id","web_name","team","now_cost","element_type"]]
teams = pd.DataFrame(bs["teams"])[["id","name"]].rename(columns={"id":"team"})

pretty = (picks_df
          .merge(players, left_on="element", right_on="id")
          .merge(teams, on="team")
          .sort_values("position"))

print(pretty[["position","web_name","name","now_cost","multiplier","is_captain","is_vice_captain"]])
