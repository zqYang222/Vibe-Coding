"""Async judging engine (Step 2).

Evaluation runs as a background task (`asyncio.create_task`) so the submit
endpoint can return `pending` immediately. Subprocesses are managed with
`asyncio.create_subprocess_exec` + `asyncio.wait_for` (TLE) and an async
psutil-based memory monitor (MLE); the event loop is never blocked.

Limit resolution (TA Q&A #2):
    problem config -> language config -> system defaults (3s / 128MB).
"""

import asyncio
import json
import shutil
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import aiofiles

from app.config import (
    DATA_DIR,
    DEFAULT_MEMORY_LIMIT,
    DEFAULT_TIME_LIMIT,
    JUDGE_LOGS_DIR,
)
from app.services import language_ops, problem_ops, submission_ops, user_ops

WORK_ROOT = DATA_DIR / "tmp"
_COMPILE_TIMEOUT = 20.0  # seconds
_MONITOR_INTERVAL = 0.05  # seconds

# Strong references so running evaluations are never garbage-collected.
_background_tasks: set = set()


def start_background(record: Dict[str, Any]) -> None:
    """Schedule an evaluation in the background (Step 2 suggests
    asyncio.create_task)."""
    task = asyncio.create_task(evaluate(record))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def resolve_limits(problem: Dict[str, Any], lang: Dict[str, Any]) -> Tuple[float, int]:
    t = problem.get("time_limit")
    m = problem.get("memory_limit")
    if t is None:
        t = lang.get("time_limit")
    if m is None:
        m = lang.get("memory_limit")
    if t is None:
        t = DEFAULT_TIME_LIMIT
    if m is None:
        m = DEFAULT_MEMORY_LIMIT
    return float(t), int(m)


def normalize_output(text: str) -> str:
    """Step 2: ignore trailing spaces on each line and trailing newlines
    at the end of the output."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    lines = [ln.rstrip() for ln in lines]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def _tokenize(cmd: str) -> List[str]:
    """Split a command template into argv WITHOUT mangling backslashes.

    shlex.split treats backslashes as escapes, which corrupts Windows paths
    such as C:\\Users\\...; this splitter only honors spaces and single/
    double quotes, keeping backslashes literal (cross-platform safe)."""
    tokens: List[str] = []
    cur: List[str] = []
    quote = None
    for ch in cmd:
        if quote is not None:
            if ch == quote:
                quote = None
            else:
                cur.append(ch)
        elif ch in ("'", '"'):
            quote = ch
        elif ch.isspace():
            if cur:
                tokens.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        tokens.append("".join(cur))
    return tokens


async def evaluate(submission: Dict[str, Any]) -> None:
    """Full judging flow for one submission (runs in the background)."""
    sid = submission["submission_id"]
    workdir = WORK_ROOT / sid
    workdir.mkdir(parents=True, exist_ok=True)
    try:
        problem = await problem_ops.get(submission["problem_id"])
        lang = await language_ops.get(submission["language"])
        if problem is None or lang is None:
            await _finish(submission, "error", error_info="problem or language not found")
            return

        time_limit, memory_limit = resolve_limits(problem, lang)
        src = workdir / f"main{lang['file_ext']}"
        exe = workdir / ("main.exe" if sys.platform == "win32" else "main")
        async with aiofiles.open(src, "w", encoding="utf-8") as f:
            await f.write(submission["code"])

        cases = problem.get("testcases", [])
        counts = len(cases) * 10

        # ---- compile phase (skipped for interpreted languages) ----
        compile_info = None
        if lang.get("compile_cmd"):
            compiled, message = await _compile(lang, src, exe, workdir)
            if not compiled:
                details = [
                    {"id": i + 1, "result": "CE", "time": 0, "memory": 0}
                    for i in range(len(cases))
                ]
                await _finish(
                    submission,
                    "success",
                    score=0,
                    counts=counts,
                    compile_info={"result": "failed", "message": message},
                    run_info={"result": "compile_error", "message": "compilation failed"},
                    details=details,
                )
                return
            compile_info = {"result": "success", "message": ""}

        # ---- run phase: one subprocess per test case ----
        details = []
        for i, case in enumerate(cases):
            status, stdout, stderr, elapsed, peak = await _run_one(
                lang, src, exe, workdir, case["input"], time_limit, memory_limit
            )
            if status == "OK":
                verdict = (
                    "AC"
                    if normalize_output(stdout) == normalize_output(case["output"])
                    else "WA"
                )
            else:
                verdict = status  # TLE / MLE / RE / UNK
            details.append(
                {
                    "id": i + 1,
                    "result": verdict,
                    "time": round(elapsed, 3),
                    "memory": round(peak, 1),
                }
            )

        score = sum(10 for d in details if d["result"] == "AC")
        run_info = {"result": "finished", "message": f"{len(details)} test cases finished"}
        await _finish(
            submission,
            "success",
            score=score,
            counts=counts,
            compile_info=compile_info,
            run_info=run_info,
            details=details,
        )
    except Exception:
        await _finish(submission, "error", error_info="internal judge error")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def _compile(lang, src, exe, workdir) -> Tuple[bool, str]:
    cmd = lang["compile_cmd"].format(src=str(src), exe=str(exe))
    argv = _tokenize(cmd)
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(workdir),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=_COMPILE_TIMEOUT
        )
    except asyncio.TimeoutError:
        return False, "compilation timed out"
    except FileNotFoundError:
        return False, "compiler not found"
    except Exception as e:  # pragma: no cover - defensive
        return False, f"compilation error: {e}"
    if proc.returncode != 0:
        message = (stderr or stdout).decode(errors="replace").strip()
        return False, message or "compilation failed"
    return True, ""


async def _run_one(lang, src, exe, workdir, input_data, time_limit, memory_limit):
    """Run the program on one test case. Returns
    (status, stdout, stderr, elapsed_seconds, peak_memory_mb) where status
    is one of OK / TLE / MLE / RE / UNK."""
    cmd = lang["run_cmd"].format(src=str(src), exe=str(exe))
    argv = _tokenize(cmd)
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=str(workdir),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        return "UNK", "", "interpreter not found", 0.0, 0.0

    holder: Dict[str, Any] = {"mle": False, "peak": 0.0}
    monitor = asyncio.create_task(_memory_monitor(proc, memory_limit, holder))
    start = time.monotonic()
    try:
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input_data.encode()), timeout=time_limit
            )
        except asyncio.TimeoutError:
            _kill(proc)
            await proc.wait()
            elapsed = time.monotonic() - start
            return "TLE", "", "", elapsed, holder.get("peak", 0.0)
        elapsed = time.monotonic() - start
    finally:
        # Give the monitor a beat to observe the final state, then stop it.
        try:
            peak = await asyncio.wait_for(asyncio.shield(monitor), timeout=1.0)
        except asyncio.TimeoutError:
            peak = holder.get("peak", 0.0)
        if not monitor.done():
            monitor.cancel()

    if holder["mle"]:
        return "MLE", "", "", elapsed, peak
    if proc.returncode != 0:
        return (
            "RE",
            stdout.decode(errors="replace"),
            stderr.decode(errors="replace"),
            elapsed,
            peak,
        )
    return (
        "OK",
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
        elapsed,
        peak,
    )


async def _memory_monitor(proc, memory_limit_mb: int, holder: Dict[str, Any]) -> float:
    """Poll the process RSS and kill it (MLE) when over the limit."""
    peak = 0.0
    try:
        import psutil

        p = psutil.Process(proc.pid)
        while proc.returncode is None:
            try:
                rss = p.memory_info().rss / (1024 ** 2)
            except psutil.NoSuchProcess:
                break
            peak = max(peak, rss)
            if rss > memory_limit_mb:
                holder["mle"] = True
                _kill(proc)
                break
            await asyncio.sleep(_MONITOR_INTERVAL)
    except ImportError:
        pass  # psutil unavailable: MLE checking disabled
    except Exception:
        pass  # defensive: never break the judge because of monitoring
    holder["peak"] = max(holder.get("peak", 0.0), peak)
    return peak


def _kill(proc) -> None:
    try:
        proc.kill()
    except ProcessLookupError:
        pass


async def _finish(
    submission: Dict[str, Any],
    status: str,
    score: Optional[int] = None,
    counts: Optional[int] = None,
    compile_info: Optional[Dict[str, str]] = None,
    run_info: Optional[Dict[str, str]] = None,
    error_info: str = "",
    details: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """Persist the final verdict and the per-test-case judge log."""
    submission["status"] = status
    submission["score"] = score
    submission["counts"] = counts
    submission["compile_info"] = compile_info
    submission["run_info"] = run_info
    submission["error_info"] = error_info

    # resolve_count counts each problem at most once per user: only the
    # FIRST fully-passing submission increments it. Updated BEFORE the
    # record is persisted so a poller that observes "success" also sees
    # the counters already applied (no race window).
    if (
        status == "success"
        and score is not None
        and counts is not None
        and score == counts
        and counts > 0
    ):
        if not await submission_ops.has_previous_pass(
            submission["user_id"], submission["problem_id"], submission["submission_id"]
        ):
            await user_ops.update_counters(submission["user_id"], resolve_delta=1)

    await submission_ops.save(submission)

    log_path = JUDGE_LOGS_DIR / f"{submission['submission_id']}.json"
    if details is None:
        # Stale logs must not survive a rejudge that errored out.
        log_path.unlink(missing_ok=True)
        return
    payload = {
        "submission_id": submission["submission_id"],
        "details": details,
        "score": score,
        "counts": counts,
    }
    async with aiofiles.open(log_path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(payload, ensure_ascii=False, indent=2))
