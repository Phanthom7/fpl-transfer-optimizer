from __future__ import annotations

import json
import pickle
import unicodedata
from pathlib import Path

import pandas as pd
import requests

ARTIFACTS_DIR = Path("artifacts")
TRAINING_FEATURES_FILE = ARTIFACTS_DIR / "training_features.csv"
MODEL_FILE = ARTIFACTS_DIR / "model.pkl"
MODEL_METADATA_FILE = ARTIFACTS_DIR / "model_metadata.json"
PREDICTIONS_FILE = ARTIFACTS_DIR / "predictions.csv"
GAMES_IN_SEASON = 38

FEATURE_COLUMNS = [
    "value",
    "ict_index",
    "creativity",
    "influence",
    "threat",
    "team_strength",
    "opp_team_strength",
    "fixture_difficulty_overall",
    "rolling_avg_3",
    "rolling_avg_5",
    "minutes",
    "was_home",
    "transfers_balance",
    "pos_DEF",
    "pos_FWD",
    "pos_GK",
    "pos_MID",
]

POSITION_MAP = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}


def ensure_artifacts_dir() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def normalize_name(name: str) -> str:
    if not name:
        return ""

    normalized = str(name).lower()
    replacements = {
        "ø": "o",
        "æ": "ae",
        "å": "a",
        "é": "e",
        "è": "e",
        "ê": "e",
        "ë": "e",
        "á": "a",
        "à": "a",
        "â": "a",
        "ä": "a",
        "í": "i",
        "ì": "i",
        "î": "i",
        "ï": "i",
        "ó": "o",
        "ò": "o",
        "ô": "o",
        "ö": "o",
        "ú": "u",
        "ù": "u",
        "û": "u",
        "ü": "u",
        "ñ": "n",
        "ć": "c",
        "č": "c",
        "ś": "s",
        "š": "s",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)

    normalized = (
        unicodedata.normalize("NFKD", normalized)
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    normalized = "".join(c for c in normalized if c.isalnum() or c.isspace())
    return " ".join(normalized.split())


def ensure_feature_columns(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()
    for column in FEATURE_COLUMNS:
        if column not in result.columns:
            result[column] = 0
    return result


def fetch_live_data() -> tuple[list[dict], list[dict], int]:
    response = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/")
    response.raise_for_status()
    payload = response.json()
    current_gw = next((event["id"] for event in payload["events"] if event["is_next"]), 38)
    return payload["elements"], payload["teams"], current_gw


def fetch_fixtures() -> list[dict]:
    response = requests.get("https://fantasy.premierleague.com/api/fixtures/")
    response.raise_for_status()
    return response.json()


def build_next_opponent_map(fixtures: list[dict], current_gw: int) -> dict[int, dict]:
    next_opp_map: dict[int, dict] = {}

    sorted_fixtures = sorted(
        (fixture for fixture in fixtures if fixture["event"] is not None),
        key=lambda fixture: (fixture["event"], fixture["kickoff_time"] or ""),
    )

    for fixture in sorted_fixtures:
        if fixture["finished"] or fixture["event"] < current_gw:
            continue

        home_team = fixture["team_h"]
        away_team = fixture["team_a"]

        if home_team not in next_opp_map:
            next_opp_map[home_team] = {
                "opp": away_team,
                "home": 1,
                "fdr": fixture["team_h_difficulty"],
            }

        if away_team not in next_opp_map:
            next_opp_map[away_team] = {
                "opp": home_team,
                "home": 0,
                "fdr": fixture["team_a_difficulty"],
            }

    return next_opp_map


def build_live_features(
    elements: list[dict],
    teams: list[dict],
    fixtures: list[dict],
    current_gw: int,
) -> pd.DataFrame:
    team_map = {team["id"]: team for team in teams}
    team_strength_map = {team["id"]: team["strength"] for team in teams}
    next_opp_map = build_next_opponent_map(fixtures, current_gw)

    rows = []
    for player in elements:
        team_id = player["team"]
        pos_id = player["element_type"]
        pos_str = POSITION_MAP[pos_id]
        next_match = next_opp_map.get(team_id, {"opp": None, "home": 0.5, "fdr": 3})
        opponent_id = next_match["opp"]

        rows.append(
            {
                "id": player["id"],
                "name": player["web_name"],
                "full_name": f"{player['first_name']} {player['second_name']}",
                "team": team_id,
                "team_short_name": team_map[team_id]["short_name"],
                "value": player["now_cost"],
                "ict_index": float(player["ict_index"]) / GAMES_IN_SEASON,
                "creativity": float(player["creativity"]) / GAMES_IN_SEASON,
                "influence": float(player["influence"]) / GAMES_IN_SEASON,
                "threat": float(player["threat"]) / GAMES_IN_SEASON,
                "minutes": player["minutes"] / GAMES_IN_SEASON,
                "transfers_balance": player["transfers_in_event"] - player["transfers_out_event"],
                "rolling_avg_3": float(player["form"]),
                "rolling_avg_5": float(player["form"]),
                "team_strength": team_strength_map.get(team_id, 3),
                "was_home": next_match["home"],
                "fixture_difficulty_overall": next_match["fdr"],
                "opp_team_strength": team_strength_map.get(opponent_id, 3) if opponent_id else 3,
                "pos_DEF": 1 if pos_str == "DEF" else 0,
                "pos_FWD": 1 if pos_str == "FWD" else 0,
                "pos_GK": 1 if pos_str == "GK" else 0,
                "pos_MID": 1 if pos_str == "MID" else 0,
                "element_type": pos_id,
                "position": pos_str,
                "status": player["status"],
                "chance_of_playing_next_round": player["chance_of_playing_next_round"],
                "now_cost": player["now_cost"],
            }
        )

    return ensure_feature_columns(pd.DataFrame(rows)).fillna(0)


def save_model_artifacts(model, metadata: dict) -> None:
    ensure_artifacts_dir()
    with MODEL_FILE.open("wb") as handle:
        pickle.dump(model, handle)
    MODEL_METADATA_FILE.write_text(json.dumps(metadata, indent=2))


def load_model_artifacts():
    with MODEL_FILE.open("rb") as handle:
        model = pickle.load(handle)
    metadata = json.loads(MODEL_METADATA_FILE.read_text())
    return model, metadata
