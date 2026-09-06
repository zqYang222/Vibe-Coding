"""AI problem-generation service (Advance module, R1-R4).

- Model config is persisted locally; the API key is never returned.
- Generation runs as a cancellable background task with live progress.
- Token usage & cost are recorded; usage is estimated (and marked) when the
  provider does not report it.
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Any, Dict, Optional

import aiofiles
import httpx

from app.config import DATA_DIR
from app.models.problem import ProblemModel
from app.services import problem_ops

AI_DIR = DATA_DIR / "ai"
CONFIG_FILE = AI_DIR / "config.json"
TASKS_DIR = AI_DIR / "tasks"

AI_DIR.mkdir(parents=True, exist_ok=True)
TASKS_DIR.mkdir(parents=True, exist_ok=True)

_lock = asyncio.Lock()
# task_id -> running asyncio.Task (for cancellation)
_running: Dict[str, asyncio.Task] = {}


# ---------------- model config ----------------

async def get_config() -> Dict[str, Any]:
    if not CONFIG_FILE.is_file():
        return {}
    try:
        async with aiofiles.open(CONFIG_FILE, encoding="utf-8") as f:
            return json.loads(await f.read())
    except (OSError, json.JSONDecodeError):
        return {}


async def set_config(cfg: Dict[str, Any]) -> None:
    async with _lock:
        existing = await get_config()
        existing.update(cfg)
        async with aiofiles.open(CONFIG_FILE, "w", encoding="utf-8") as f:
            await f.write(json.dumps(existing, ensure_ascii=False, indent=2))


async def public_config() -> Dict[str, Any]:
    """Config view safe to return: api_key is never exposed (R2)."""
    cfg = await get_config()
    return {
        "provider_url": cfg.get("provider_url", ""),
        "model": cfg.get("model", ""),
        "api_key_configured": bool(cfg.get("api_key")),
        "input_price": cfg.get("input_price"),
        "output_price": cfg.get("output_price"),
        "price_unit": cfg.get("price_unit"),
    }


# ---------------- task records ----------------

def _task_path(task_id: str):
    return TASKS_DIR / f"{task_id}.json"


async def _next_task_id() -> str:
    ids = [p.stem for p in TASKS_DIR.glob("*.json")]
    seq = max((int(i.split("-")[-1]) for i in ids if i.split("-")[-1].isdigit()), default=0)
    return f"ai-{seq + 1}"


async def create_task(user_id: str, requirement: str, problem_id: Optional[str]) -> str:
    async with _lock:
        task_id = await _next_task_id()
        record = {
            "task_id": task_id,
            "user_id": user_id,
            "requirement": requirement,
            "problem_id": problem_id,
            "status": "pending",
            "progress": "任务已创建",
            "result": None,
            "usage": None,
            "created_time": datetime.now().isoformat(timespec="seconds"),
        }
        async with aiofiles.open(_task_path(task_id), "w", encoding="utf-8") as f:
            await f.write(json.dumps(record, ensure_ascii=False, indent=2))
        return task_id


async def get_task(task_id: str) -> Optional[Dict[str, Any]]:
    path = _task_path(task_id)
    if not path.is_file():
        return None
    try:
        async with aiofiles.open(path, encoding="utf-8") as f:
            return json.loads(await f.read())
    except (OSError, json.JSONDecodeError):
        return None


async def update_task(record: Dict[str, Any]) -> None:
    async with aiofiles.open(_task_path(record["task_id"]), "w", encoding="utf-8") as f:
        await f.write(json.dumps(record, ensure_ascii=False, indent=2))


# ---------------- generation ----------------

_SYSTEM_PROMPT = (
    "你是一名专业的 OJ 出题助手。请根据用户需求生成一道编程题，"
    "只输出一个 JSON 对象（不要输出任何其他文字），字段为："
    "id(唯一字符串，如 P1001)、title、description、input_description、"
    "output_description、samples(数组，元素含 input/output)、constraints、"
    "testcases(数组，元素含 input/output，至少 3 个，覆盖边界情况)、"
    "hint(可为空串)、source、tags(数组)、time_limit(秒,数字)、"
    "memory_limit(MB,整数)、author、difficulty。"
)


def start_task(task_id: str) -> None:
    """Launch generation in the background (asyncio.create_task)."""
    task = asyncio.create_task(run_task(task_id))
    _running[task_id] = task
    task.add_done_callback(lambda t: _running.pop(task_id, None))


def cancel_task(task_id: str) -> bool:
    task = _running.get(task_id)
    if task is None:
        return False
    task.cancel()
    return True


async def run_task(task_id: str) -> None:
    record = await get_task(task_id)
    if record is None or record.get("status") == "cancelled":
        return
    cfg = await get_config()
    provider_url = (cfg.get("provider_url") or "").rstrip("/")
    model = cfg.get("model") or ""
    api_key = cfg.get("api_key") or ""
    if not provider_url or not model or not api_key:
        record["status"] = "failed"
        record["progress"] = "模型配置不完整，请先完成模型配置"
        await update_task(record)
        return

    record["status"] = "running"
    record["progress"] = "正在连接模型..."
    await update_task(record)

    requirement = record["requirement"]
    # If a problem_id was given, feed the existing problem into the prompt
    # so the model can reference/modify it (api.md 建议路径).
    if record.get("problem_id"):
        existing = await problem_ops.get(record["problem_id"])
        if existing:
            requirement = (
                requirement
                + "\n\n参考/修改已有题目（JSON）：\n"
                + json.dumps(existing, ensure_ascii=False)
            )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": requirement},
    ]
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "temperature": 0.7,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    url = f"{provider_url}/chat/completions"
    parts = []
    usage = None
    last_update = datetime.now()
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=15.0)
        ) as client:
            async with client.stream("POST", url, json=payload, headers=headers) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="replace")[:500]
                    raise RuntimeError(f"模型接口返回 {resp.status_code}: {body}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data_str = line[len("data:"):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue
                    choices = chunk.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        piece = delta.get("content")
                        if piece:
                            parts.append(piece)
                    if chunk.get("usage"):
                        usage = chunk["usage"]
                    # Live progress (R3): persist every ~1.5s.
                    now = datetime.now()
                    if (now - last_update).total_seconds() >= 1.5:
                        last_update = now
                        record["progress"] = f"正在生成题目（已生成 {len(''.join(parts))} 字符）..."
                        await update_task(record)
                    if record.get("status") == "cancelled":
                        raise asyncio.CancelledError()

        content = "".join(parts)
        if not content.strip():
            raise RuntimeError("模型未返回任何内容")
        result = _extract_json(content)
        problem = ProblemModel(**result)
        record["result"] = problem.model_dump()
        record["status"] = "completed"
        record["progress"] = "命题完成"
        record["usage"] = _calc_usage(payload, content, usage, cfg)
        await update_task(record)
    except asyncio.CancelledError:
        record["status"] = "cancelled"
        record["progress"] = "任务已中断"
        await update_task(record)
    except Exception as e:
        record["status"] = "failed"
        record["progress"] = f"命题失败: {e}"
        await update_task(record)


def _extract_json(content: str) -> Dict[str, Any]:
    match = re.search(r"```(?:json)?\s*(.*?)```", content, re.S)
    if match:
        content = match.group(1)
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("模型输出中未找到 JSON 对象")
    return json.loads(content[start : end + 1])


def _calc_usage(payload: Dict[str, Any], content: str, usage, cfg) -> Dict[str, Any]:
    price_unit = float(cfg.get("price_unit") or 1_000_000)
    in_price = float(cfg.get("input_price") or 0)
    out_price = float(cfg.get("output_price") or 0)
    if usage:
        in_tokens = int(usage.get("prompt_tokens") or 0)
        out_tokens = int(usage.get("completion_tokens") or 0)
        estimated = False
    else:
        # Fallback estimate (documented in the report): ~4 chars per token.
        in_tokens = max(1, len(json.dumps(payload["messages"], ensure_ascii=False)) // 4)
        out_tokens = max(1, len(content) // 4)
        estimated = True
    total = in_tokens + out_tokens
    cost = round(in_tokens / price_unit * in_price + out_tokens / price_unit * out_price, 6)
    return {
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
        "total_tokens": total,
        "cost": cost,
        "currency": "USD",
        "estimated": estimated,
    }
