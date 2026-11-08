"""python -m src.features.run"""
from __future__ import annotations

import logging
import time

from src.config import PROCESSED_DIR
from src.features.build import build
from src.ingest.io import to_parquet_safe


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    t = time.time()
    df = build()
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    to_parquet_safe(df, PROCESSED_DIR / "features.parquet")
    logging.info("features rows=%d cols=%d in %.0fs", len(df), df.shape[1], time.time() - t)


if __name__ == "__main__":
    main()
