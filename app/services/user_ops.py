"""User storage & operations (Step 4).

Users are one JSON file per user under data/users/. Passwords are hashed
with bcrypt. The initial admin (admin / admintestpassword) is created at
startup.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiofiles
import bcrypt

from app.config import (
    INITIAL_ADMIN_PASSWORD,
    INITIAL_ADMIN_USERNAME,
    LOGS_DIR,
    USERS_DIR,
)

VALID_ROLES = {"user", "admin", "banned"}

_id_lock = asyncio.Lock()


def _path(user_id: str):
    return USERS_DIR / f"{user_id}.json"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


async def set_password(user_id: str, new_password: str) -> None:
    """Reset a user's password (forgot-password flow)."""
    user = await get(user_id)
    if user is None:
        return
    user["password_hash"] = hash_password(new_password)
    await save(user)


async def _next_id() -> str:
    ids = [int(p.stem) for p in USERS_DIR.glob("*.json") if p.stem.isdigit()]
    return str(max(ids, default=0) + 1)


async def get(user_id: str) -> Optional[Dict[str, Any]]:
    path = _path(user_id)
    if not path.is_file():
        return None
    try:
        async with aiofiles.open(path, encoding="utf-8") as f:
            return json.loads(await f.read())
    except (OSError, json.JSONDecodeError):
        return None


async def get_by_username(username: str) -> Optional[Dict[str, Any]]:
    for path in USERS_DIR.glob("*.json"):
        user = await get(path.stem)
        if user and user.get("username") == username:
            return user
    return None


async def exists_username(username: str) -> bool:
    return await get_by_username(username) is not None


async def create(username: str, password: str, role: str = "user") -> Dict[str, Any]:
    async with _id_lock:
        user_id = await _next_id()
        record = {
            "user_id": user_id,
            "username": username,
            "password_hash": hash_password(password),
            "role": role,
            "join_time": datetime.now().strftime("%Y-%m-%d"),
            "submit_count": 0,
            "resolve_count": 0,
        }
        async with aiofiles.open(_path(user_id), "w", encoding="utf-8") as f:
            await f.write(json.dumps(record, ensure_ascii=False, indent=2))
        return record


async def save(record: Dict[str, Any]) -> None:
    async with aiofiles.open(_path(record["user_id"]), "w", encoding="utf-8") as f:
        await f.write(json.dumps(record, ensure_ascii=False, indent=2))


async def list_all() -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for path in USERS_DIR.glob("*.json"):
        user = await get(path.stem)
        if user:
            records.append(user)
    records.sort(key=lambda u: int(u["user_id"]))
    return records


async def update_role(user_id: str, role: str) -> None:
    user = await get(user_id)
    if user is None:
        return
    user["role"] = role
    await save(user)


async def update_counters(
    user_id: str, submit_delta: int = 0, resolve_delta: int = 0
) -> None:
    user = await get(user_id)
    if user is None:
        return
    user["submit_count"] = max(0, int(user.get("submit_count", 0)) + submit_delta)
    user["resolve_count"] = max(0, int(user.get("resolve_count", 0)) + resolve_delta)
    await save(user)


async def ensure_initial_admin() -> None:
    """Create the initial admin account on startup (api.md 系统初始化)."""
    if await get_by_username(INITIAL_ADMIN_USERNAME) is not None:
        return
    await create(INITIAL_ADMIN_USERNAME, INITIAL_ADMIN_PASSWORD, role="admin")


async def log_admin_op(admin_id: str, target_id: str, role: str) -> None:
    """Append an operation log: who changed whose role and when (Step 4)."""
    entry = {
        "admin_id": admin_id,
        "target_id": target_id,
        "role": role,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    async with aiofiles.open(LOGS_DIR / "admin_ops.jsonl", "a", encoding="utf-8") as f:
        await f.write(json.dumps(entry, ensure_ascii=False) + "\n")
