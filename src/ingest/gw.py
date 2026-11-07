"""Gameweek normalisation. 2019-20 restarted after COVID as GW39-47; map to 30-38."""
from __future__ import annotations

import pandas as pd

COVID_SEASON = "2019-20"
COVID_OFFSET = 9  # GW39..47 -> 30..38


def normalize_gw(season: str, gw: pd.Series) -> pd.Series:
    gw = pd.to_numeric(gw, errors="coerce").astype("Int64")
    if season == COVID_SEASON:
        gw = gw.where(gw < 39, gw - COVID_OFFSET)
    return gw
