"""Problem storage operations (Step 1).

Problems are stored as one JSON file per problem under data/problems/.
All file I/O is async (aiofiles), per the assignment's async requirement.

TA Q&A rulings implemented here:
- #4: deleting a problem also deletes its testcases, submissions, judge
  logs and access logs;
- #8: deleting a problem rolls back the related users' submit_count and
  resolve_count.
"""

import json
import re
from typing import Any, Dict, List, Optional

import aiofiles

from app.config import (
    ACCESS_LOGS_DIR,
    JUDGE_LOGS_DIR,
    PROBLEMS_DIR,
    SUBMISSIONS_DIR,
    USERS_DIR,
)
from app.models.problem import ProblemModel
from app.services import log_ops

# Problem ids are restricted to safe filename characters; this also blocks
# path traversal attempts (security requirement).
_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def valid_id(problem_id: str) -> bool:
    return bool(_ID_PATTERN.match(problem_id))


def _path(problem_id: str):
    return PROBLEMS_DIR / f"{problem_id}.json"


async def exists(problem_id: str) -> bool:
    return _path(problem_id).is_file()


async def get(problem_id: str) -> Optional[Dict[str, Any]]:
    path = _path(problem_id)
    if not path.is_file():
        return None
    async with aiofiles.open(path, encoding="utf-8") as f:
        return json.loads(await f.read())


async def list_all() -> List[Dict[str, str]]:
    """Brief info of every problem: [{id, title}]."""
    items: List[Dict[str, str]] = []
    for path in sorted(PROBLEMS_DIR.glob("*.json")):
        try:
            async with aiofiles.open(path, encoding="utf-8") as f:
                data = json.loads(await f.read())
            items.append({"id": data["id"], "title": data["title"]})
        except (json.JSONDecodeError, KeyError):
            continue  # skip malformed problem files
    return items


async def save(problem: ProblemModel) -> None:
    path = _path(problem.id)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(
            json.dumps(problem.model_dump(), ensure_ascii=False, indent=2)
        )


async def delete(problem_id: str) -> bool:
    """Delete the problem file, cascading to related data (TA Q&A #4/#8)."""
    path = _path(problem_id)
    if not path.is_file():
        return False
    await _cascade_delete(problem_id)
    await log_ops.clear_visibility(problem_id)
    path.unlink()
    return True


async def _read_json(path) -> Optional[Dict[str, Any]]:
    try:
        async with aiofiles.open(path, encoding="utf-8") as f:
            return json.loads(await f.read())
    except (OSError, json.JSONDecodeError):
        return None


async def _write_json(path, data: Dict[str, Any]) -> None:
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=2))


async def _cascade_delete(problem_id: str) -> None:
    """Remove submissions / judge logs / access logs of a problem and revert
    the counters of the users involved."""

    # 1. Collect every submission record of this problem.
    submissions: List[Dict[str, Any]] = []
    if SUBMISSIONS_DIR.is_dir():
        for path in SUBMISSIONS_DIR.glob("*.json"):
            data = await _read_json(path)
            if data and data.get("problem_id") == problem_id:
                submissions.append(data)

    # 2. Revert per-user counters (TA Q&A #8). A problem counts as solved
    #    (resolve_count) when some submission of that user got full marks.
    submit_delta: Dict[str, int] = {}
    passed_users: Dict[str, bool] = {}
    for sub in submissions:
        uid = sub.get("user_id")
        if not uid:
            continue
        submit_delta[uid] = submit_delta.get(uid, 0) + 1
        if sub.get("status") == "success" and sub.get("score") == sub.get("counts"):
            passed_users[uid] = True

    for uid, delta in submit_delta.items():
        upath = USERS_DIR / f"{uid}.json"
        user = await _read_json(upath) if upath.is_file() else None
        if not user:
            continue
        user["submit_count"] = max(0, int(user.get("submit_count", 0)) - delta)
        if passed_users.get(uid):
            user["resolve_count"] = max(0, int(user.get("resolve_count", 0)) - 1)
        await _write_json(upath, user)

    # 3. Remove submission files, judge logs and access logs.
    for sub in submissions:
        sid = sub.get("submission_id")
        if sid:
            (JUDGE_LOGS_DIR / f"{sid}.json").unlink(missing_ok=True)
            for path in SUBMISSIONS_DIR.glob(f"{sid}.json"):
                path.unlink(missing_ok=True)
    if ACCESS_LOGS_DIR.is_dir():
        for path in ACCESS_LOGS_DIR.glob("*.json"):
            data = await _read_json(path)
            if data and data.get("problem_id") == problem_id:
                path.unlink(missing_ok=True)
