"""Phase 0 evals: audit + plan."""
import re
import subprocess

import pytest

from tests.evals.conftest import ROOT

BASE = "81a5e8e"  # repo state before rebuild
BUDGET_H = 12.0   # 2 days x 6 h floor


def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def plan_rows():
    """Phase table rows of PLAN.md as dicts keyed by header."""
    lines = (ROOT / "PLAN.md").read_text().splitlines()
    for i, line in enumerate(lines):
        if line.startswith("| #") and "Phase" in line:
            header = [c.strip() for c in line.strip("|").split("|")]
            rows = []
            for row in lines[i + 2:]:
                if not row.startswith("|"):
                    break
                cells = [c.strip() for c in row.strip("|").split("|")]
                rows.append(dict(zip(header, cells)))
            return header, rows
    raise AssertionError("phase table not found in PLAN.md")


def hours(cell: str) -> float:
    m = re.search(r"[\d.]+", cell or "")
    return float(m.group()) if m else 0.0


@pytest.mark.critical
def test_audit_covers_all_files(ev):
    """Audit table covers 100% of repo files"""
    files = git("ls-tree", "-r", "--name-only", BASE).split()
    audit = (ROOT / "AUDIT.md").read_text()
    rows = [l for l in audit.splitlines() if l.startswith("| `")]
    covered = [f for f in files if any(f"`{f}`" in r.split("|")[1] and re.search(r"keep|adapt|archive", r) for r in rows)]
    missing = sorted(set(files) - set(covered))
    ev.check(not missing, f"{len(covered)}/{len(files)}", "100%", f"missing: {missing}" if missing else "")


@pytest.mark.pass_gate
def test_plan_fits_budget(ev):
    """PLAN.md must-have hours fit 2-day budget"""
    header, rows = plan_rows()
    col = "Must hrs" if "Must hrs" in header else "Hrs"
    total = sum(hours(r.get(col)) for r in rows if r.get("#", "").strip("*").strip().isdigit() or r.get("#") == "E")
    ev.check(total <= BUDGET_H, f"{total} h ({col})", f"<= {BUDGET_H} h")


@pytest.mark.good
def test_must_vs_stretch_split(ev):
    """Must-have vs stretch clearly split"""
    header, rows = plan_rows()
    text = (ROOT / "PLAN.md").read_text()
    phases = [r for r in rows if r.get("#", "").isdigit() and int(r["#"]) >= 1]
    has_cols = "Must-have" in header and "Stretch" in header
    all_must = all(r.get("Must-have") for r in phases)
    has_priority = bool(re.search(r"stretch priority", text, re.I))
    ok = has_cols and all_must and has_priority and len(phases) >= 6
    ev.check(ok, f"cols={has_cols} every_phase_has_must={all_must} priority_list={has_priority}", "all true")
