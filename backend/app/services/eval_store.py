"""SQLite-based evaluation result storage.

Stores eval run summaries and metadata in a lightweight local database,
keeping full per-case detail in JSON. Supports history queries and
trend comparisons without polluting git with timestamped JSON files.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = _BACKEND_ROOT / "evals" / "evals.db"


def _get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS eval_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_utc TEXT NOT NULL,
            dataset TEXT NOT NULL,
            k INTEGER NOT NULL,
            use_query_rewrite INTEGER NOT NULL DEFAULT 0,
            is_comparison INTEGER NOT NULL DEFAULT 0,
            git_commit TEXT,
            llm_provider TEXT,
            model_name TEXT,
            embedding_model TEXT,
            chunk_size INTEGER,
            chunk_overlap INTEGER,
            bm25_weight REAL,
            summary_json TEXT NOT NULL,
            full_result_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_eval_runs_timestamp
            ON eval_runs(timestamp_utc DESC);
    """)


_conn: sqlite3.Connection | None = None


def get_store_connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = _get_connection()
        _ensure_schema(_conn)
    return _conn


def save_eval(payload: dict[str, Any]) -> int:
    """Save a complete eval payload to the store. Returns the row id."""
    conn = get_store_connection()

    metadata = payload.get("metadata", {})
    summary = payload.get("summary", {})
    is_comparison = 1 if "baseline" in payload else 0

    conn.execute(
        """
        INSERT INTO eval_runs (
            timestamp_utc, dataset, k, use_query_rewrite, is_comparison,
            git_commit, llm_provider, model_name, embedding_model,
            chunk_size, chunk_overlap, bm25_weight,
            summary_json, full_result_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payload.get("timestamp_utc", datetime.now(UTC).isoformat()),
            payload.get("dataset", ""),
            payload.get("k", 4),
            1 if payload.get("use_query_rewrite") else 0,
            is_comparison,
            metadata.get("git_commit"),
            metadata.get("llm_provider"),
            metadata.get("model_name"),
            metadata.get("embedding_model"),
            metadata.get("chunk_size"),
            metadata.get("chunk_overlap"),
            metadata.get("bm25_weight"),
            json.dumps(summary, ensure_ascii=False),
            json.dumps(payload, ensure_ascii=False),
        ),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_latest() -> dict[str, Any] | None:
    """Return the most recent eval run (full detail)."""
    conn = get_store_connection()
    row = conn.execute(
        "SELECT full_result_json FROM eval_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["full_result_json"])


def get_history(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent eval summaries (without per-case detail)."""
    conn = get_store_connection()
    rows = conn.execute(
        """
        SELECT id, timestamp_utc, dataset, k, use_query_rewrite, is_comparison,
               git_commit, llm_provider, model_name, embedding_model,
               chunk_size, chunk_overlap, bm25_weight, summary_json
        FROM eval_runs
        ORDER BY id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    results = []
    for row in rows:
        entry: dict[str, Any] = {
            "id": row["id"],
            "timestamp_utc": row["timestamp_utc"],
            "dataset": row["dataset"],
            "k": row["k"],
            "use_query_rewrite": bool(row["use_query_rewrite"]),
            "is_comparison": bool(row["is_comparison"]),
            "git_commit": row["git_commit"],
            "llm_provider": row["llm_provider"],
            "model_name": row["model_name"],
            "embedding_model": row["embedding_model"],
            "chunk_size": row["chunk_size"],
            "chunk_overlap": row["chunk_overlap"],
            "bm25_weight": row["bm25_weight"],
            "summary": json.loads(row["summary_json"]),
        }
        results.append(entry)
    return results


def get_by_id(eval_id: int) -> dict[str, Any] | None:
    """Return the full eval result for a given id."""
    conn = get_store_connection()
    row = conn.execute(
        "SELECT full_result_json FROM eval_runs WHERE id = ?", (eval_id,)
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["full_result_json"])
