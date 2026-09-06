"""Submission endpoints (Steps 2 & 3).

Error priority follows api.md: 401 > 403 > 400 > 429 > 409 > 404 > 500.
The rate limit is per user+problem (TA Q&A #7).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.submission import SubmissionCreate
from app.services import auth, judge, language_ops, problem_ops, submission_ops, user_ops
from app.services.auth import CurrentUser
from app.utils import parse_body

router = APIRouter(prefix="/api/submissions", tags=["submissions"])


@router.post("")
async def submit(
    request: Request, current_user: CurrentUser = Depends(auth.get_current_user)
):
    data = await parse_body(request)
    try:
        payload = SubmissionCreate(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid body: {e}")

    # 429 comes before 404 per api.md's error priority.
    if not submission_ops.check_rate_limit(current_user.user_id, payload.problem_id):
        raise HTTPException(status_code=429, detail="too many submissions")
    if not await problem_ops.exists(payload.problem_id):
        raise HTTPException(status_code=404, detail="problem not found")
    if not await language_ops.exists(payload.language):
        raise HTTPException(status_code=404, detail="language not found")

    sid = await submission_ops.create(
        current_user.user_id, payload.problem_id, payload.language, payload.code
    )
    record = await submission_ops.get(sid)
    # submit_count counts every submission (api.md).
    await user_ops.update_counters(current_user.user_id, submit_delta=1)
    judge.start_background(record)
    return {"code": 200, "msg": "success", "data": {"submission_id": sid, "status": "pending"}}


@router.get("")
async def list_submissions(
    user_id: Optional[str] = None,
    problem_id: Optional[str] = None,
    status: Optional[str] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    current_user: CurrentUser = Depends(auth.get_current_user),
):
    # Permission check first (api.md: 401 > 403 > 400 ...).
    if (
        user_id is not None
        and user_id != current_user.user_id
        and not current_user.is_admin
    ):
        raise HTTPException(status_code=403, detail="permission denied")
    # Primary conditions may not both be empty.
    if user_id is None and problem_id is None:
        raise HTTPException(
            status_code=400, detail="user_id and problem_id cannot both be empty"
        )
    # Pagination rules (api.md): page without page_size is invalid; page_size
    # alone means the first page; both empty means return everything.
    if page is not None and page_size is None:
        raise HTTPException(status_code=400, detail="page_size is required when page is given")
    if page is not None and page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if page_size is not None and page_size < 1:
        raise HTTPException(status_code=400, detail="page_size must be >= 1")

    records = await submission_ops.list_all()
    matched = [
        r
        for r in records
        if (user_id is None or r["user_id"] == user_id)
        and (problem_id is None or r["problem_id"] == problem_id)
        and (status is None or r["status"] == status)
    ]
    # Without user_id: admins see all records of the problem, regular users
    # only their own.
    if user_id is None and not current_user.is_admin:
        matched = [r for r in matched if r["user_id"] == current_user.user_id]

    if page is None and page_size is None:
        page_items = matched
    else:
        p = page if page is not None else 1
        start = (p - 1) * page_size
        page_items = matched[start : start + page_size]

    items = []
    for r in page_items:
        item = {
            "submission_id": r["submission_id"],
            "user_id": r["user_id"],
            "problem_id": r["problem_id"],
            "language": r["language"],
            "status": r["status"],
            "created_time": r.get("created_time", ""),
        }
        # pending/error items only carry id + status (api.md); success items
        # additionally carry the score summary.
        if r["status"] == "success":
            item["score"] = r.get("score")
            item["counts"] = r.get("counts")
        items.append(item)

    return {
        "code": 200,
        "msg": "success",
        "data": {"total": len(matched), "submissions": items},
    }


@router.get("/{submission_id}")
async def get_submission(
    submission_id: str, current_user: CurrentUser = Depends(auth.get_current_user)
):
    record = await submission_ops.get(submission_id)
    if record is None:
        raise HTTPException(status_code=404, detail="submission not found")
    if not current_user.is_admin and record["user_id"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="permission denied")

    data = {
        "submission_id": record["submission_id"],
        "user_id": record["user_id"],
        "problem_id": record["problem_id"],
        "language": record["language"],
        "status": record["status"],
        # Fields not produced yet stay null for pending submissions (api.md).
        "score": record.get("score"),
        "counts": record.get("counts"),
        "compile_info": record.get("compile_info"),
        "run_info": record.get("run_info"),
        "error_info": record.get("error_info", ""),
    }
    return {"code": 200, "msg": "success", "data": data}


@router.put("/{submission_id}/rejudge")
async def rejudge(
    submission_id: str, _: CurrentUser = Depends(auth.get_current_admin)
):
    record = await submission_ops.get(submission_id)
    if record is None:
        raise HTTPException(status_code=404, detail="submission not found")
    # Rejudging overwrites the original submission's content (api.md).
    record.update(
        {
            "status": "pending",
            "score": None,
            "counts": None,
            "compile_info": None,
            "run_info": None,
            "error_info": "",
        }
    )
    await submission_ops.save(record)
    judge.start_background(record)
    return {
        "code": 200,
        "msg": "rejudge started",
        "data": {"submission_id": submission_id, "status": "pending"},
    }
