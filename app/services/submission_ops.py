"""Submission storage & rate limiting (Steps 2 & 3).

Rate limit (TA Q&A #7): the 3-per-minute cap is counted per user AND per
problem, not globally.
"""

import asyncio
import json
import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiofiles

from app.config import (
    SUBMISSIONS_DIR,
    SUBMIT_RATE_LIMIT,
    SUBMIT_RATE_WINDOW_SECONDS,
)

# (user_id, problem_id) -> timestamps of recent submits (in-memory).
_rate_records: Dict[Tuple[str, str], deque] = defaultdict(deque)

# Guards id allocation so two concurrent submits never collide.
_id_lock = asyncio.Lock()


def _path(submission_id: str):
    return SUBMISSIONS_DIR / f"{submission_id}.json"


async def _next_id() -> str:
    ids = [int(p.stem) for p in SUBMISSIONS_DIR.glob("*.json") if p.stem.isdigit()]
    return str(max(ids, default=0) + 1)


def check_rate_limit(user_id: str, problem_id: str) -> bool:
    """Return True if the submit is allowed, False if rate-limited."""
    now = time.monotonic()
    q = _rate_records[(user_id, problem_id)]
    while q and now - q[0] > SUBMIT_RATE_WINDOW_SECONDS:
        q.popleft()
    if len(q) >= SUBMIT_RATE_LIMIT:
        return False
    q.append(now)
    return True


def reset_rate_limits() -> None:
    """Forget all rate-limit history (used by /api/reset/)."""
    _rate_records.clear()


async def has_previous_pass(user_id: str, problem_id: str, current_id: str) -> bool:
    """Whether an EARLIER submission of the same user already fully passed
    this problem (used to keep resolve_count at most 1 per problem)."""
    try:
        current = int(current_id)
    except ValueError:
        current = 0
    for path in SUBMISSIONS_DIR.glob("*.json"):
        try:
            sid = int(path.stem)
        except ValueError:
            continue
        if sid >= current:
            continue
        try:
            async with aiofiles.open(path, encoding="utf-8") as f:
                record = json.loads(await f.read())
        except (OSError, json.JSONDecodeError):
            continue
        if (
            record.get("user_id") == user_id
            and record.get("problem_id") == problem_id
            and record.get("status") == "success"
            and record.get("score") == record.get("counts")
            and record.get("counts")
        ):
            return True
    return False


async def create(user_id: str, problem_id: str, language: str, code: str) -> str:
    """Create a pending submission record and return its id."""
    async with _id_lock:
        sid = await _next_id()
        record = {
            "submission_id": sid,
            "user_id": user_id,
            "problem_id": problem_id,
            "language": language,
            "code": code,
            "status": "pending",
            "score": None,
            "counts": None,
            "compile_info": None,
            "run_info": None,
            "error_info": "",
            "created_time": datetime.now().isoformat(timespec="seconds"),
        }
        async with aiofiles.open(_path(sid), "w", encoding="utf-8") as f:
            await f.write(json.dumps(record, ensure_ascii=False, indent=2))
        return sid


async def get(submission_id: str) -> Optional[Dict[str, Any]]:
    path = _path(submission_id)
    if not path.is_file():
        return None
    try:
        async with aiofiles.open(path, encoding="utf-8") as f:
            return json.loads(await f.read())
    except (OSError, json.JSONDecodeError):
        return None


async def save(record: Dict[str, Any]) -> None:
    async with aiofiles.open(_path(record["submission_id"]), "w", encoding="utf-8") as f:
        await f.write(json.dumps(record, ensure_ascii=False, indent=2))


async def list_all() -> List[Dict[str, Any]]:
    """All submission records, newest first."""
    records: List[Dict[str, Any]] = []
    for path in SUBMISSIONS_DIR.glob("*.json"):
        try:
            async with aiofiles.open(path, encoding="utf-8") as f:
                records.append(json.loads(await f.read()))
        except (OSError, json.JSONDecodeError):
            continue
    records.sort(key=lambda r: int(r["submission_id"]), reverse=True)
    return records
