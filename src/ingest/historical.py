"""Historical ingest (completed seasons) from vaastav/Fantasy-Premier-League."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.config import AUX_SEASONS, HIST_SEASONS, RAW_DIR, VAASTAV_BASE
from src.ingest.http import FetchError, fetch_bytes
from src.ingest.gw import normalize_gw
from src.ingest.io import read_csv_bytes, to_parquet_safe

log = logging.getLogger(__name__)

# name -> (relative path, required)
FILES = {
    "merged_gw": ("gws/merged_gw.csv", True),
    "players_raw": ("players_raw.csv", True),
    "fixtures": ("fixtures.csv", True),
    "teams": ("teams.csv", True),
}
OUT = RAW_DIR / "vaastav"


def ingest_season(season: str, force: bool = False, only: list[str] | None = None) -> dict:
    out_dir = OUT / season
    manifest_path = out_dir / "_manifest.json"
    if manifest_path.exists() and not force:
        log.info("%s: already ingested, skipping", season)
        return json.loads(manifest_path.read_text())

    manifest = {"season": season, "source": VAASTAV_BASE, "files": {},
                "ingested_at": datetime.now(timezone.utc).isoformat()}
    for name, (rel, required) in FILES.items():
        if only and name not in only:
            continue
        url = f"{VAASTAV_BASE}/{season}/{rel}"
        try:
            raw = fetch_bytes(url)
        except FetchError as exc:
            if required:
                raise
            log.info("%s: optional %s missing (%s)", season, name, exc)
            continue
        df, enc = read_csv_bytes(raw)
        df.insert(0, "season", season)
        # raw columns untouched; add normalised GW alongside
        if name == "merged_gw":
            df["gw"] = normalize_gw(season, df["GW"])
        elif name == "fixtures":
            df["gw"] = normalize_gw(season, df["event"])
        to_parquet_safe(df, out_dir / f"{name}.parquet")
        manifest["files"][name] = {"rows": len(df), "cols": df.shape[1], "encoding": enc}
        log.info("%s: %s rows=%d enc=%s", season, name, len(df), enc)

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2))
    return manifest


def ingest_all(seasons=HIST_SEASONS, force: bool = False) -> list[dict]:
    return [ingest_season(s, force=force) for s in seasons]


def ingest_aux(force: bool = False) -> None:
    for s in AUX_SEASONS:
        ingest_season(s, force=force, only=["players_raw"])
