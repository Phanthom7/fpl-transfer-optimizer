"""python -m src.clean.run"""
from __future__ import annotations

import logging

from src.clean import dq
from src.clean.build import build
from src.config import INTERIM_DIR
from src.ingest.io import to_parquet_safe


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    df = build()
    to_parquet_safe(df, INTERIM_DIR / "player_gw.parquet")
    r = dq.write(df, INTERIM_DIR)
    logging.info("player_gw rows=%d dup_keys=%d", r["rows"], r["duplicate_keys"])


if __name__ == "__main__":
    main()
