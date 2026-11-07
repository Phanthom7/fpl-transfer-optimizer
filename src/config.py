"""Project-wide paths and constants."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
HTTP_CACHE_DIR = RAW_DIR / "_http_cache"

HIST_SEASONS = ["2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25", "2025-26"]
LIVE_SEASON = "2026-27"
ALL_SEASONS = HIST_SEASONS + [LIVE_SEASON]

VAASTAV_BASE = "https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data"
FPL_API_BASE = "https://fantasy.premierleague.com/api"

REQUEST_DELAY_S = float(os.getenv("FPL_REQUEST_DELAY_S", "1.0"))
USER_AGENT = "fpl-transfer-optimizer/0.1 (personal research project)"
