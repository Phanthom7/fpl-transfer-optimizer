"""python -m src.ingest.run [--force] [--seasons ...] [--no-api]

Historical seasons from vaastav; live season from the official FPL API only."""
from __future__ import annotations

import argparse
import logging

from src.config import HIST_SEASONS
from src.ingest.fpl_api import ingest_live_api
from src.ingest.historical import ingest_all, ingest_aux


def main(argv=None) -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true", help="re-download completed seasons")
    p.add_argument("--seasons", nargs="*", default=HIST_SEASONS)
    p.add_argument("--no-api", action="store_true")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    ingest_aux(force=a.force)
    ingest_all(a.seasons, force=a.force)
    if not a.no_api:
        ingest_live_api()


if __name__ == "__main__":
    main()
