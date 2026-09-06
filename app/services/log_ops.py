"""Judge-log access, log visibility & access audit (Step 5).

- Judge logs (per test case) live in data/logs/judge/{sid}.json.
- Access audit entries: one JSON file each under data/logs/access/.
- Per-problem log visibility registry: data/log_visibility.json.

TA Q&A #9: GET /api/logs/access/ follows GET /api/submissions/: the primary
conditions may not both be empty (-> 400).
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiofiles

from app.config import ACCESS_LOGS_DIR, DATA_DIR, JUDGE_LOGS_DIR

VISIBILITY_FILE = DATA_DIR / "log_visibility.json"

_lock = asyncio.Lock()


# ---------- log visibility ----------

async def _load_visibility() -> Dict[str, bool]:
    if not VISIBILITY_FILE.is_file():
        return {}
    try:
        async with aiofiles.open(VISIBILITY_FILE, encoding="utf-8") as f:
            return json.loads(await f.read())
    except (OSError, json.JSONDecodeError):
        return {}


async def get_visibility(problem_id: str) -> bool:
    return (await _load_visibility()).get(problem_id, False)


async def set_visibility(problem_id: str, public: bool) -> None:
    async with _lock:
        registry = await _load_visibility()
        registry[problem_id] = public
        async with aiofiles.open(VISIBILITY_FILE, "w", encoding="utf-8") as f:
            await f.write(json.dumps(registry, ensure_ascii=False, indent=2))


async def clear_visibility(problem_id: str) -> None:
    async with _lock:
        registry = await _load_visibility()
        registry.pop(problem_id, None)
        async with aiofiles.open(VISIBILITY_FILE, "w", encoding="utf-8") as f:
            await f.write(json.dumps(registry, ensure_ascii=False, indent=2))


async def reset_visibility() -> None:
    VISIBILITY_FILE.unlink(missing_ok=True)


# ---------- judge logs ----------

async def read_judge_log(submission_id: str) -> Optional[Dict[str, Any]]:
    path = JUDGE_LOGS_DIR / f"{submission_id}.json"
    if not path.is_file():
        return None
    try:
        async with aiofiles.open(path, encoding="utf-8") as f:
            return json.loads(await f.read())
    except (OSError, json.JSONDecodeError):
        return None


# ---------- access audit ----------

async def _next_seq() -> str:
    seqs = [int(p.stem) for p in ACCESS_LOGS_DIR.glob("*.json") if p.stem.isdigit()]
    return str(max(seqs, default=0) + 1)


async def record_access(user_id: str, problem_id: str, status: str) -> None:
    """Append one audit entry. api.md: action is always view_logs here."""
    async with _lock:
        seq = await _next_seq()
        entry = {
            "user_id": user_id,
            "problem_id": problem_id,
            "action": "view_logs",
            "time": datetime.now().strftime("%Y-%m-%d"),
            "status": status,
        }
        async with aiofiles.open(
            ACCESS_LOGS_DIR / f"{seq}.json", "w", encoding="utf-8"
        ) as f:
            await f.write(json.dumps(entry, ensure_ascii=False, indent=2))


async def list_access() -> List[Dict[str, Any]]:
    pairs: List[tuple] = []
    for path in ACCESS_LOGS_DIR.glob("*.json"):
        if not path.stem.isdigit():
            continue
        try:
            async with aiofiles.open(path, encoding="utf-8") as f:
                pairs.append((int(path.stem), json.loads(await f.read())))
        except (OSError, json.JSONDecodeError):
            continue
    pairs.sort(key=lambda p: p[0], reverse=True)
    return [entry for _, entry in pairs]
