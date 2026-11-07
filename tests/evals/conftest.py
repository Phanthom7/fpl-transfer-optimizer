"""Eval gate plumbing: one test = one check. Writes evals/results/phaseN.{json,md}."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "evals" / "results"
TIER_MARKS = {"critical": "CRITICAL", "pass_gate": "PASS", "good": "GOOD"}
_records: dict[str, dict] = {}


def _tier(item) -> str:
    for mark, tier in TIER_MARKS.items():
        if item.get_closest_marker(mark):
            return tier
    raise pytest.UsageError(f"{item.nodeid}: eval test needs a tier marker")


def _phase(item) -> int:
    m = re.search(r"test_phase(\d+)_", item.fspath.basename)
    return int(m.group(1)) if m else -1


def _rec(item) -> dict:
    doc = (item.function.__doc__ or item.name).strip().splitlines()[0]
    return _records.setdefault(item.nodeid, {
        "phase": _phase(item), "check": doc, "tier": _tier(item),
        "value": None, "threshold": None, "note": "", "ok": None, "status": None,
    })


class Ev:
    def __init__(self, item):
        self.item = item
        self.rec = _rec(item)

    def check(self, ok: bool, value, threshold, note: str = "") -> None:
        self.rec.update(value=_fmt(value), threshold=str(threshold), note=note, ok=bool(ok))
        if not ok and self.rec["tier"] != "GOOD":
            pytest.fail(f"{self.rec['check']}: value={self.rec['value']} threshold={threshold} {note}", pytrace=False)


def _fmt(v):
    if isinstance(v, float):
        return round(v, 4)
    if isinstance(v, (int, str, bool)) or v is None:
        return v
    return str(v)


@pytest.fixture
def ev(request) -> Ev:
    return Ev(request.node)


def pytest_collection_modifyitems(items):
    for item in items:
        _rec(item)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    rec = _rec(item)
    if rep.when == "setup" and rep.failed:
        rec.update(status="FAIL", note=_short(rep))
    elif rep.when == "call":
        if rep.failed:
            rec["status"] = "FAIL"
            if not rec["note"]:
                rec["note"] = _short(rep)
        elif rec["tier"] == "GOOD" and rec["ok"] is False:
            rec["status"] = "WARN"
        else:
            rec["status"] = "PASS"


def _short(rep) -> str:
    text = str(rep.longrepr).strip().splitlines()
    return (text[-1] if text else "")[:300]


def pytest_sessionfinish(session):
    phases = sorted({r["phase"] for r in _records.values() if r["status"]})
    RESULTS.mkdir(parents=True, exist_ok=True)
    order = {"CRITICAL": 0, "PASS": 1, "GOOD": 2}
    for ph in phases:
        rows = sorted((r for r in _records.values() if r["phase"] == ph and r["status"]),
                      key=lambda r: order[r["tier"]])
        blocked = any(r["status"] == "FAIL" and r["tier"] in ("CRITICAL", "PASS") for r in rows)
        out = {"phase": ph, "gate": "BLOCKED" if blocked else "OPEN",
               "run_at": datetime.now(timezone.utc).isoformat(), "checks": rows}
        (RESULTS / f"phase{ph}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
        md = [f"# Phase {ph} scorecard", "", f"Gate: **{out['gate']}**  ", f"Run: {out['run_at']}", "",
              "| check | tier | value | threshold | status | note |", "|---|---|---|---|---|---|"]
        for r in rows:
            md.append(f"| {r['check']} | {r['tier']} | {r['value']} | {r['threshold']} | {r['status']} | {r['note'].replace('|', '/')} |")
        (RESULTS / f"phase{ph}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
