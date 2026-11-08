"""Phase 1 evals: ingest. Real data + real network."""
import hashlib
import json
import time

import pandas as pd
import pytest

from src import config
from src.ingest import http
from src.ingest.fpl_api import FPLClient, ingest_live_api
from src.ingest.historical import OUT as VAASTAV, ingest_all
from tests.evals.conftest import ROOT

API_DIR = config.RAW_DIR / "fpl_api"
PLAYER_RANGE = (550, 950)


def latest_api_dir():
    dirs = sorted(p for p in API_DIR.glob("*") if p.is_dir())
    assert dirs, "no FPL API snapshot in data/raw/fpl_api"
    return dirs[-1]


def hashes(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*.parquet"))}


@pytest.mark.critical
def test_six_plus_seasons(ev):
    """6+ historical seasons loaded"""
    loaded = [s for s in config.HIST_SEASONS if (VAASTAV / s / "merged_gw.parquet").exists()]
    ev.check(len(loaded) >= 6, len(loaded), ">= 6", ",".join(loaded))


@pytest.mark.critical
def test_every_gw_present(ev):
    """Every scheduled GW present per season (2019/20 remapped)"""
    problems = []
    for s in config.HIST_SEASONS:
        gw = pd.read_parquet(VAASTAV / s / "merged_gw.parquet", columns=["gw"])["gw"]
        fx = pd.read_parquet(VAASTAV / s / "fixtures.parquet", columns=["gw"])["gw"]
        scheduled, present = set(fx.dropna().astype(int)), set(gw.dropna().astype(int))
        if present != scheduled or not present <= set(range(1, 39)):
            problems.append(f"{s}: missing={sorted(scheduled - present)} extra={sorted(present - scheduled)}")
    # live season: every finished GW in API player history
    d = latest_api_dir()
    events = pd.read_parquet(d / "events.parquet")
    finished = set(events.loc[events["finished"].astype(str) == "True", "id"].astype(int))
    hist = set(pd.read_parquet(d / "element_history.parquet")["round"].astype(int))
    if not finished <= hist:
        problems.append(f"{config.LIVE_SEASON}: missing={sorted(finished - hist)}")
    ev.check(not problems, f"{len(config.HIST_SEASONS) + 1 - len(problems)}/{len(config.HIST_SEASONS) + 1} seasons complete",
             "all seasons", "; ".join(problems))


@pytest.mark.critical
@pytest.mark.network
def test_rerun_identical(ev):
    """Rerun ingest = identical row counts + file hashes"""
    ingest_all(force=True)
    ingest_live_api()
    api = latest_api_dir()
    h1, a1 = hashes(VAASTAV), hashes(api)
    m1 = {s: json.loads((VAASTAV / s / "_manifest.json").read_text())["files"] for s in config.HIST_SEASONS}
    ingest_all(force=True)
    ingest_live_api()
    h2, a2 = hashes(VAASTAV), hashes(api)
    m2 = {s: json.loads((VAASTAV / s / "_manifest.json").read_text())["files"] for s in config.HIST_SEASONS}
    diff = [k for k in set(h1) | set(h2) if h1.get(k) != h2.get(k)] + [k for k in set(a1) | set(a2) if a1.get(k) != a2.get(k)]
    ev.check(not diff and m1 == m2, f"{len(h1) + len(a1)} files, {len(diff)} differ, rows_equal={m1 == m2}", "0 differ", ",".join(diff))


@pytest.mark.critical
def test_raw_is_parquet(ev):
    """Raw saved as parquet in data/raw/, rows match manifest"""
    bad = []
    n = 0
    for s in config.HIST_SEASONS:
        for name, meta in json.loads((VAASTAV / s / "_manifest.json").read_text())["files"].items():
            p = VAASTAV / s / f"{name}.parquet"
            n += 1
            if not p.exists() or len(pd.read_parquet(p)) != meta["rows"]:
                bad.append(f"{s}/{name}")
    for p in latest_api_dir().glob("*.parquet"):
        n += 1
        pd.read_parquet(p)
    stray = [str(p) for p in config.RAW_DIR.rglob("*.csv")]
    ev.check(not bad and not stray, f"{n} parquet files ok, bad={len(bad)}, stray_csv={len(stray)}", "0 bad", ",".join(bad + stray))


@pytest.mark.critical
@pytest.mark.network
def test_live_api_endpoints(ev):
    """Live API: bootstrap-static, fixtures, element-summary, event live OK"""
    c = FPLClient(ttl_s=0)  # force real calls
    bs = c.bootstrap()
    fx = c.fixtures()
    eid = int(bs["elements"][0]["id"])
    es = c.element_summary(eid)
    last = max(e["id"] for e in bs["events"] if e["finished"])
    live = c.event_live(last)
    ok = (len(bs["elements"]) > 500 and len(bs["teams"]) == 20 and len(fx) == 380
          and "history" in es and len(live["elements"]) > 500)
    ev.check(ok, f"elements={len(bs['elements'])} fixtures={len(fx)} history={len(es.get('history', []))} live={len(live['elements'])}",
             "all 4 endpoints return data")


@pytest.mark.critical
@pytest.mark.network
def test_rate_limit_and_cache(ev, tmp_path, monkeypatch):
    """Rate limit (>=1 s/host) + disk cache in place"""
    http._last_call.clear()
    t0 = time.time()
    http.fetch_bytes(f"{config.FPL_API_BASE}/fixtures/?event=1", cache_dir=tmp_path)
    http.fetch_bytes(f"{config.FPL_API_BASE}/fixtures/?event=2", cache_dir=tmp_path)
    gap = time.time() - t0

    def no_network(*a, **k):
        raise AssertionError("network hit on cached url")

    monkeypatch.setattr(http.requests, "get", no_network)
    cached = http.fetch_bytes(f"{config.FPL_API_BASE}/fixtures/?event=1", cache_dir=tmp_path)
    ok = config.REQUEST_DELAY_S >= 1.0 and gap >= 1.0 and len(cached) > 0
    ev.check(ok, f"delay_cfg={config.REQUEST_DELAY_S}s two_calls={gap:.2f}s cache_hit=True", ">= 1.0 s, cache hit")


@pytest.mark.pass_gate
@pytest.mark.network
def test_current_gw_matches_site(ev):
    """Snapshot current GW matches live FPL site"""
    snap = pd.read_parquet(latest_api_dir() / "events.parquet")
    snap_gw = int(snap.loc[snap["is_current"].astype(str) == "True", "id"].iloc[0])
    live = FPLClient(ttl_s=0).bootstrap()["events"]
    live_gw = next(e["id"] for e in live if e["is_current"])
    ev.check(snap_gw == live_gw, f"snapshot={snap_gw} site={live_gw}", "equal")


@pytest.mark.pass_gate
def test_player_counts_plausible(ev):
    """Per-season player counts in plausible range"""
    counts = {s: len(pd.read_parquet(VAASTAV / s / "players_raw.parquet", columns=["id"])) for s in config.HIST_SEASONS}
    counts[config.LIVE_SEASON] = len(pd.read_parquet(latest_api_dir() / "elements.parquet", columns=["id"]))
    lo, hi = PLAYER_RANGE
    out = {s: n for s, n in counts.items() if not lo <= n <= hi}
    sr = pd.Series(counts)
    z = ((sr - sr.mean()) / sr.std()).abs()
    flagged = z[z > 1.5].index.tolist()
    ev.check(not out, f"min={sr.min()} max={sr.max()}", f"{lo}-{hi}",
             f"out_of_range={out} outliers(|z|>1.5)={flagged}")


@pytest.mark.good
def test_xg_coverage(ev):
    """xG/xA coverage where source has it"""
    cov = {}
    for s in config.HIST_SEASONS:
        df = pd.read_parquet(VAASTAV / s / "merged_gw.parquet")
        if "expected_goals" in df.columns:
            cov[s] = min(df["expected_goals"].notna().mean(), df["expected_assists"].notna().mean())
    h = pd.read_parquet(latest_api_dir() / "element_history.parquet")
    cov[config.LIVE_SEASON] = min(h["expected_goals"].notna().mean(), h["expected_assists"].notna().mean())
    worst = min(cov.values())
    ev.check(worst >= 0.90, worst, ">= 0.90", " ".join(f"{k}={v:.3f}" for k, v in cov.items()))


@pytest.mark.good
def test_source_justified(ev):
    """Data source choice justified in DECISIONS.md"""
    rows = [l for l in (ROOT / "DECISIONS.md").read_text().splitlines() if "vaastav" in l.lower() and "source" in l.lower()]
    why = rows[0].strip("|").split("|")[-1].strip() if rows else ""
    ev.check(bool(rows) and len(why) > 40, f"rows={len(rows)} why_len={len(why)}", "row present, reason > 40 chars")
