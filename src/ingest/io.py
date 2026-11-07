"""CSV decoding and parquet writing that never mangles names."""
from __future__ import annotations

import io
import json
import unicodedata
from pathlib import Path

import pandas as pd

ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


def decode(raw: bytes) -> tuple[str, str]:
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    raise ValueError("undecodable bytes")  # latin-1 never fails, kept for safety


def read_csv_bytes(raw: bytes) -> tuple[pd.DataFrame, str]:
    text, enc = decode(raw)
    text = unicodedata.normalize("NFC", text)
    df = pd.read_csv(io.StringIO(text), low_memory=False, on_bad_lines="warn")
    return df, enc


def to_parquet_safe(df: pd.DataFrame, path: Path) -> None:
    """Object columns -> string (or JSON for nested) so pyarrow never chokes."""
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object:
            if out[col].map(lambda v: isinstance(v, (list, dict))).any():
                out[col] = out[col].map(lambda v: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
            out[col] = out[col].astype("string")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    out.to_parquet(tmp, index=False)
    tmp.replace(path)  # atomic: no half-written files on rerun
