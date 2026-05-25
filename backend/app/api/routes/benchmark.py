from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter

router = APIRouter()

RESULTS_DIR = Path(__file__).resolve().parents[3] / "evals" / "results"


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
