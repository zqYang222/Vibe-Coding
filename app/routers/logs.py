"""Evaluation log & audit endpoints (Step 5).

Visibility rules:
- admin or the owner always sees the per-test-case details;
- other users only when the problem's public_cases is True;
- every logged-in access on an existing submission is audited with its
  status (api.md: skip auditing for 401 / 404 / 400).
"""

import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.services import auth, log_ops, problem_ops, submission_ops
from app.services.auth import CurrentUser

router = APIRouter(tags=["logs"])


@router.get("/api/submissions/{submission_id}/log")
async def get_submission_log(
    submission_id: str, current_user: CurrentUser = Depends(auth.get_current_user)
):
    record = await submission_ops.get(submission_id)
    if record is None:
        raise HTTPException(status_code=404, detail="submission not found")

    allowed = current_user.is_admin or record["user_id"] == current_user.user_id
    if not allowed:
        allowed = await log_ops.get_visibility(record["problem_id"])
    await log_ops.record_access(
        current_user.user_id, record["problem_id"], "200" if allowed else "403"
    )
    if not allowed:
        raise HTTPException(status_code=403, detail="permission denied")

    log = await log_ops.read_judge_log(submission_id)
    details = log["details"] if log else []
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "details": details,
            "score": record.get("score"),
            "counts": record.get("counts"),
        },
    }


@router.put("/api/problems/{problem_id}/log_visibility")
async def set_log_visibility(
    problem_id: str,
    request: Request,
    _: CurrentUser = Depends(auth.get_current_admin),
):
    if not await problem_ops.exists(problem_id):
        raise HTTPException(status_code=404, detail="problem not found")
    # Body is optional entirely; public_cases defaults to False.
    body = await request.body()
    if not body.strip():
        data = {}
    else:
        try:
            data = json.loads(body)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid body: not valid JSON")
        if not isinstance(data, dict):
            raise HTTPException(status_code=400, detail="Invalid body: expected a JSON object")
    public = data.get("public_cases", False)
    if not isinstance(public, bool):
        raise HTTPException(status_code=400, detail="public_cases must be a bool")
    await log_ops.set_visibility(problem_id, public)
    return {
        "code": 200,
        "msg": "log visibility updated",
        "data": {"problem_id": problem_id, "public_cases": public},
    }


@router.get("/api/logs/access/")
async def list_access(
    user_id: Optional[str] = None,
    problem_id: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    _: CurrentUser = Depends(auth.get_current_admin),
):
    # TA Q&A #9: same primary-condition rule as GET /api/submissions/.
    if user_id is None and problem_id is None:
        raise HTTPException(
            status_code=400, detail="user_id and problem_id cannot both be empty"
        )
    if page is not None and page_size is None:
        raise HTTPException(status_code=400, detail="page_size is required when page is given")
    if page is not None and page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if page_size is not None and page_size < 1:
        raise HTTPException(status_code=400, detail="page_size must be >= 1")

    entries = await log_ops.list_access()
    matched = [
        e
        for e in entries
        if (user_id is None or e["user_id"] == user_id)
        and (problem_id is None or e["problem_id"] == problem_id)
    ]
    if page is None and page_size is None:
        items = matched
    else:
        p = page if page is not None else 1
        start = (p - 1) * page_size
        items = matched[start : start + page_size]

    data = [
        {
            "user_id": e["user_id"],
            "problem_id": e["problem_id"],
            "action": e["action"],
            "time": e["time"],
            "status": e["status"],
        }
        for e in items
    ]
    return {"code": 200, "msg": "success", "data": data}
