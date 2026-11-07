"""SQL sandbox over the project's CSV tables.

Every CSV in the repo root (and in artifacts/, if it exists) is loaded into an
in-memory SQLite database, one table per file. The database is read-only, so
queries can't change anything on disk or in the loaded data.

Run:
    streamlit run sql_sandbox.py
"""
from __future__ import annotations

import re
import sqlite3
import time
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
CSV_DIRS = [ROOT, ROOT / "artifacts"]
MAX_DISPLAY_ROWS = 10_000

EXAMPLES = {
    "Top 20 scorers, 2022-23": (
        "SELECT name, position, team_x AS team, SUM(total_points) AS points,\n"
        "       SUM(goals_scored) AS goals, SUM(assists) AS assists\n"
        "FROM cleaned_merged_seasons\n"
        "WHERE season_x = '2022-23'\n"
        "GROUP BY name, position, team_x\n"
        "ORDER BY points DESC\n"
        "LIMIT 20;"
    ),
    "Points per season": (
        "SELECT season_x, COUNT(DISTINCT name) AS players, SUM(total_points) AS points\n"
        "FROM cleaned_merged_seasons\n"
        "GROUP BY season_x\n"
        "ORDER BY season_x;"
    ),
    "Best predicted value (v3)": (
        "SELECT full_name, team_short_name, position, now_cost / 10.0 AS price,\n"
        "       predicted_points,\n"
        "       ROUND(predicted_points / (now_cost / 10.0), 2) AS points_per_million\n"
        "FROM fpl_predictions_v3\n"
        "WHERE status = 'a'\n"
        "ORDER BY points_per_million DESC\n"
        "LIMIT 25;"
    ),
    "List tables": "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name;",
}


def table_name_for(path: Path) -> str:
    """Turn a file name like 'fpl_2024:25.csv' into a valid SQL identifier."""
    name = re.sub(r"\W", "_", path.stem)
    if name[0].isdigit():
        name = f"t_{name}"
    if path.parent.name == "artifacts":
        name = f"artifacts_{name}"
    return name


def find_csvs() -> list[Path]:
    files: list[Path] = []
    for d in CSV_DIRS:
        if d.is_dir():
            files.extend(sorted(d.glob("*.csv")))
    return files


@st.cache_resource(show_spinner="Loading CSVs into SQLite…")
def load_database(signature: tuple) -> tuple[sqlite3.Connection, dict[str, Path]]:
    # `signature` (file paths + mtimes) only exists so the cache refreshes when a CSV changes.
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    tables: dict[str, Path] = {}
    for path in find_csvs():
        table = table_name_for(path)
        df = pd.read_csv(path, low_memory=False)
        df.to_sql(table, conn, index=False)
        tables[table] = path
    conn.execute("PRAGMA query_only = ON")
    return conn, tables


def run_query(conn: sqlite3.Connection, sql: str) -> pd.DataFrame:
    return pd.read_sql_query(sql, conn)


st.set_page_config(page_title="FPL SQL Sandbox", layout="wide")
st.title("FPL SQL Sandbox")
st.caption("Read-only SQLite over every CSV in the project. Each file is one table.")

signature = tuple((str(p), p.stat().st_mtime) for p in find_csvs())
conn, tables = load_database(signature)

with st.sidebar:
    st.header("Tables")
    for table, path in tables.items():
        rows = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        with st.expander(f"{table}  ·  {rows:,} rows"):
            st.caption(str(path.relative_to(ROOT)))
            st.dataframe(
                pd.DataFrame([(c[1], c[2]) for c in cols], columns=["column", "type"]),
                hide_index=True,
                width="stretch",
            )
    if st.button("Reload CSVs"):
        load_database.clear()
        st.rerun()

example = st.selectbox("Start from an example", ["(none)", *EXAMPLES])
if "sql" not in st.session_state:
    st.session_state.sql = EXAMPLES["Top 20 scorers, 2022-23"]
if example != "(none)" and st.session_state.get("last_example") != example:
    st.session_state.sql = EXAMPLES[example]
st.session_state.last_example = example

sql = st.text_area("SQL", key="sql", height=220)

if st.button("Run", type="primary") or st.session_state.get("auto_ran") is None:
    st.session_state.auto_ran = True
    start = time.perf_counter()
    try:
        result = run_query(conn, sql)
    except Exception as exc:  # show SQL errors inline instead of crashing the page
        st.error(f"{type(exc).__name__}: {exc}")
    else:
        elapsed = time.perf_counter() - start
        shown = result.head(MAX_DISPLAY_ROWS)
        note = f" (showing first {MAX_DISPLAY_ROWS:,})" if len(result) > MAX_DISPLAY_ROWS else ""
        st.success(f"{len(result):,} rows in {elapsed:.2f}s{note}")
        st.dataframe(shown, width="stretch", hide_index=True)
        st.download_button(
            "Download full result as CSV",
            result.to_csv(index=False).encode(),
            file_name="query_result.csv",
            mime="text/csv",
        )
