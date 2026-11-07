"""Official FPL API client (bootstrap-static, fixtures, element-summary, event live, entry)."""
from __future__ import annotations

import json
import logging
from datetime import date

import pandas as pd

from src.config import FPL_API_BASE, RAW_DIR
from src.ingest.http import FetchError, fetch_bytes
from src.ingest.io import to_parquet_safe

log = logging.getLogger(__name__)
OUT = RAW_DIR / "fpl_api"


class FPLClient:
    def __init__(self, base: str = FPL_API_BASE, ttl_s: float = 3600):
        self.base = base
        self.ttl_s = ttl_s

    def _get(self, path: str, ttl_s: float | None = None) -> dict | list:
        return json.loads(fetch_bytes(f"{self.base}/{path}", ttl_s=self.ttl_s if ttl_s is None else ttl_s))

    def bootstrap(self) -> dict:
        return self._get("bootstrap-static/")

    def fixtures(self) -> list:
        return self._get("fixtures/")

    def element_summary(self, element_id: int) -> dict:
        return self._get(f"element-summary/{element_id}/")

    def event_live(self, gw: int) -> dict:
        return self._get(f"event/{gw}/live/")

    def entry(self, team_id: int) -> dict:
        return self._get(f"entry/{team_id}/", ttl_s=600)

    def entry_history(self, team_id: int) -> dict:
        return self._get(f"entry/{team_id}/history/", ttl_s=600)

    def entry_picks(self, team_id: int, gw: int) -> dict:
        return self._get(f"entry/{team_id}/event/{gw}/picks/", ttl_s=600)

    def reachable(self) -> bool:
        try:
            self.bootstrap()
            return True
        except FetchError as exc:
            log.warning("FPL API unreachable: %s", exc)
            return False


def ingest_live_api(client: FPLClient | None = None, element_summaries: bool = False) -> dict | None:
    """Snapshot live tables to data/raw/fpl_api/<date>/. Returns None if API unreachable."""
    client = client or FPLClient()
    try:
        bs = client.bootstrap()
        fx = client.fixtures()
    except FetchError as exc:
        log.warning("FPL API unreachable, falling back to vaastav mirror: %s", exc)
        return None

    out = OUT / date.today().isoformat()
    tables = {
        "elements": pd.DataFrame(bs["elements"]),
        "teams": pd.DataFrame(bs["teams"]),
        "events": pd.DataFrame(bs["events"]),
        "element_types": pd.DataFrame(bs["element_types"]),
        "fixtures": pd.DataFrame(fx),
    }
    finished = [e["id"] for e in bs["events"] if e.get("finished")]
    live_rows = []
    for gw in finished:
        for el in client.event_live(gw)["elements"]:
            live_rows.append({"gw": gw, "element": el["id"], **el["stats"]})
    tables["event_live"] = pd.DataFrame(live_rows)

    if element_summaries:
        hist = []
        for eid in tables["elements"]["id"]:
            hist.extend(client.element_summary(int(eid)).get("history", []))
        tables["element_history"] = pd.DataFrame(hist)

    summary = {}
    for name, df in tables.items():
        to_parquet_safe(df, out / f"{name}.parquet")
        summary[name] = len(df)
    log.info("FPL API snapshot: %s", summary)
    return summary
