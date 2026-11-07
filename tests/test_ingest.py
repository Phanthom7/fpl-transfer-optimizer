import json

import pandas as pd
import pytest

from src.ingest import fpl_api, historical, http
from src.ingest.io import read_csv_bytes, to_parquet_safe

NAMES = ["Ødegaard", "Gyökeres", "Mitrović", "Diakité", "Fábio Vieira", "Đurić", "Łukasz"]


def test_utf8_names_roundtrip(tmp_path):
    raw = ("name,total_points\n" + "\n".join(f"{n},{i}" for i, n in enumerate(NAMES))).encode("utf-8")
    df, enc = read_csv_bytes(raw)
    to_parquet_safe(df, tmp_path / "x.parquet")
    back = pd.read_parquet(tmp_path / "x.parquet")
    assert back["name"].tolist() == NAMES
    assert enc == "utf-8-sig"


def test_cp1252_fallback_keeps_accents():
    raw = "name,pts\nBuendía,3\nLindelöf,2\n".encode("cp1252")
    df, enc = read_csv_bytes(raw)
    assert enc == "cp1252"
    assert df["name"].tolist() == ["Buendía", "Lindelöf"]


def test_nfc_normalisation():
    decomposed = "Odégaard"  # e + combining acute
    df, _ = read_csv_bytes(f"name\n{decomposed}\n".encode())
    assert df["name"][0] == "Odégaard"


def test_nested_columns_serialised(tmp_path):
    df = pd.DataFrame({"id": [1], "stats": [[{"a": 1}]]})
    to_parquet_safe(df, tmp_path / "n.parquet")
    assert json.loads(pd.read_parquet(tmp_path / "n.parquet")["stats"][0]) == [{"a": 1}]


def test_fetch_uses_cache(tmp_path, monkeypatch):
    calls = []

    class Resp:
        status_code = 200
        content = b"hello"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(http.requests, "get", lambda *a, **k: calls.append(1) or Resp())
    for _ in range(3):
        assert http.fetch_bytes("https://x.test/a", cache_dir=tmp_path, delay_s=0) == b"hello"
    assert len(calls) == 1


def test_fetch_404_raises(tmp_path, monkeypatch):
    class Resp:
        status_code = 404

    monkeypatch.setattr(http.requests, "get", lambda *a, **k: Resp())
    with pytest.raises(http.FetchError):
        http.fetch_bytes("https://x.test/missing", cache_dir=tmp_path, delay_s=0)


@pytest.fixture
def fake_vaastav(tmp_path, monkeypatch):
    calls = []
    csvs = {
        "merged_gw.csv": "name,element,GW,total_points\nØdegaard,1,1,8\n",
        "players_raw.csv": "id,code,web_name\n1,184029,Ødegaard\n",
        "fixtures.csv": "id,event\n1,1\n",
        "teams.csv": "id,name\n1,Arsenal\n",
    }

    def fake_fetch(url, ttl_s=None, **_):
        calls.append(url)
        key = url.rsplit("/", 1)[-1]
        if key not in csvs:
            raise http.FetchError("404")
        return csvs[key].encode()

    monkeypatch.setattr(historical, "fetch_bytes", fake_fetch)
    monkeypatch.setattr(historical, "OUT", tmp_path)
    return calls, tmp_path


def test_season_ingest_idempotent(fake_vaastav):
    calls, out = fake_vaastav
    m1 = historical.ingest_season("2020-21")
    n = len(calls)
    m2 = historical.ingest_season("2020-21")
    assert len(calls) == n  # second run: no fetches
    assert m1["files"] == m2["files"]
    df = pd.read_parquet(out / "2020-21" / "merged_gw.parquet")
    assert df["name"][0] == "Ødegaard" and (df["season"] == "2020-21").all()


def test_force_redownloads(fake_vaastav):
    calls, _ = fake_vaastav
    historical.ingest_season("2020-21")
    n = len(calls)
    historical.ingest_season("2020-21", force=True)
    assert len(calls) == 2 * n


def test_api_unreachable_returns_none(monkeypatch):
    def boom(*a, **k):
        raise http.FetchError("blocked")

    monkeypatch.setattr(fpl_api, "fetch_bytes", boom)
    assert fpl_api.ingest_live_api() is None
