from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

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
async def run_benchmark(k: int = 4, use_query_rewrite: bool = False):
    """Run evals/run_eval.py and return the generated result filename."""
    cmd = ["python", "evals/run_eval.py", "--k", str(k), "--write-results"]
    if use_query_rewrite:
        cmd.append("--use-query-rewrite")

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
