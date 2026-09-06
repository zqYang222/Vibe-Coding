"""Language registry (Step 2).

TA Q&A #6: registering a language does NOT install any compiler. It only
records how to compile/run submissions, assuming the environment already
exists. Built-ins `python` and `cpp` are pre-registered on demand.
"""

import asyncio
import json
import os
import shutil
import sys
from typing import Dict, List, Optional

import aiofiles

from app.config import DATA_DIR
from app.models.language import LanguageModel

LANG_FILE = DATA_DIR / "languages.json"

_lock = asyncio.Lock()


def _find_python() -> str:
    """Resolve a real python interpreter.

    Windows Store app-execution aliases (WindowsApps\\python*.exe) are
    skipped: they are stubs that exit non-zero when spawned directly."""
    candidates = []
    for name in ("python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    candidates.append(sys.executable)  # the interpreter we run under: real
    for cand in candidates:
        if not cand:
            continue
        try:
            resolved = os.path.realpath(cand)
        except OSError:
            resolved = cand
        if "WindowsApps" in resolved:
            continue
        if os.path.isfile(resolved):
            return resolved
    return sys.executable


async def _load() -> Dict[str, dict]:
    if not LANG_FILE.is_file():
        return {}
    try:
        async with aiofiles.open(LANG_FILE, encoding="utf-8") as f:
            return json.loads(await f.read())
    except (OSError, json.JSONDecodeError):
        return {}


async def _save(registry: Dict[str, dict]) -> None:
    async with aiofiles.open(LANG_FILE, "w", encoding="utf-8") as f:
        await f.write(json.dumps(registry, ensure_ascii=False, indent=2))


def _builtins() -> Dict[str, dict]:
    py = _find_python()
    return {
        "python": {
            "name": "python",
            "file_ext": ".py",
            "compile_cmd": None,
            "run_cmd": f"{py} {{src}}",
            "time_limit": 1.0,
            "memory_limit": 128,
        },
        "cpp": {
            "name": "cpp",
            "file_ext": ".cpp",
            "compile_cmd": "g++ {src} -o {exe}",
            "run_cmd": "{exe}",
            "time_limit": 1.0,
            "memory_limit": 128,
        },
    }


async def ensure_builtins() -> None:
    """Register built-in languages, refreshing their config on every call so
    a stale interpreter path (e.g. a store alias resolved earlier) never
    survives. User-registered languages with other names are untouched."""
    async with _lock:
        registry = await _load()
        for name, cfg in _builtins().items():
            if name not in registry or registry[name] != cfg:
                registry[name] = cfg
        await _save(registry)


async def exists(name: str) -> bool:
    await ensure_builtins()
    return name in await _load()


async def get(name: str) -> Optional[dict]:
    await ensure_builtins()
    return (await _load()).get(name)


async def register(lang: LanguageModel) -> None:
    """Register (or overwrite) a language configuration."""
    async with _lock:
        registry = await _load()
        registry[lang.name] = lang.model_dump()
        await _save(registry)


async def list_names() -> List[str]:
    await ensure_builtins()
    return sorted((await _load()).keys())
