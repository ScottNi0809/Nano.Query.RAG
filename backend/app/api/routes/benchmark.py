from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from app.services.eval_store import get_by_id, get_history, get_latest, save_eval

router = APIRouter()

RESULTS_DIR = Path(__file__).resolve().parents[3] / "evals" / "results"
BACKEND_DIR = Path(__file__).resolve().parents[3]


def _load_result(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data


@router.get("/benchmark/results")
async def list_benchmark_results():
    """Return a list of available eval result files (most recent first)."""
    if not RESULTS_DIR.is_dir():
        return []

    files = sorted(RESULTS_DIR.glob("eval_*.json"), reverse=True)
    items = []
    for f in files:
        data = _load_result(f)
        if data is None:
            continue
        items.append({
            "filename": f.name,
            "timestamp_utc": data.get("timestamp_utc"),
            "k": data.get("k"),
            "use_query_rewrite": data.get("use_query_rewrite"),
            "is_comparison": "baseline" in data,
        })
    return items


@router.get("/benchmark/results/{filename}")
async def get_benchmark_result(filename: str):
    """Return the full eval result JSON for a given filename."""
    safe_name = Path(filename).name
    path = RESULTS_DIR / safe_name
    if not path.is_file() or not path.suffix == ".json":
        return {"error": "not found"}
    data = _load_result(path)
    if data is None:
        return {"error": "invalid file"}
    return data


@router.post("/benchmark/run")
async def run_benchmark(k: int = 4, use_query_rewrite: bool = False, seed: bool = True):
    """Run evals/run_eval.py and return the generated result filename.

    By default, --seed is enabled to ensure ChromaDB is populated with docs/
    before evaluation, guaranteeing reproducible results across environments.
    """
    cmd = ["python", "evals/run_eval.py", "--k", str(k), "--write-results"]
    if use_query_rewrite:
        cmd.append("--use-query-rewrite")
    if seed:
        cmd.append("--seed")

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(BACKEND_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        return {
            "success": False,
            "error": stderr.decode(errors="replace")[-2000:],
        }

    # Find the newest result file written
    if RESULTS_DIR.is_dir():
        files = sorted(RESULTS_DIR.glob("eval_*.json"), reverse=True)
        newest = files[0].name if files else None
    else:
        newest = None

    return {"success": True, "filename": newest}


# ---- SQLite-backed history endpoints ----


@router.get("/benchmark/latest")
async def benchmark_latest():
    """Return the most recent eval run (full detail) from SQLite store."""
    result = get_latest()
    if result is None:
        return {"error": "no evaluations found"}
    return result


@router.get("/benchmark/history")
async def benchmark_history(limit: int = Query(default=20, ge=1, le=100)):
    """Return recent eval summaries (no per-case detail) for trend display."""
    return get_history(limit=limit)


@router.get("/benchmark/{eval_id:int}")
async def benchmark_detail(eval_id: int):
    """Return the full eval result for a given SQLite row id."""
    result = get_by_id(eval_id)
    if result is None:
        return {"error": "not found"}
    return result


@router.post("/benchmark/import")
async def import_existing_results():
    """One-time import: load existing JSON result files into SQLite store."""
    if not RESULTS_DIR.is_dir():
        return {"imported": 0}

    files = sorted(RESULTS_DIR.glob("eval_*.json"))
    imported = 0
    for f in files:
        data = _load_result(f)
        if data is None:
            continue
        save_eval(data)
        imported += 1
    return {"imported": imported}
