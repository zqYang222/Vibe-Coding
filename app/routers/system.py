"""System maintenance endpoints (POST /api/reset/ for auto-testing)."""

from fastapi import APIRouter, Depends, Request

from app.config import (
    ACCESS_LOGS_DIR,
    JUDGE_LOGS_DIR,
    PROBLEMS_DIR,
    SUBMISSIONS_DIR,
    USERS_DIR,
)
from app.services import auth, language_ops, log_ops, submission_ops, user_ops
from app.services.auth import CurrentUser

router = APIRouter(tags=["system"])


@router.post("/api/reset/")
async def reset(request: Request, _: CurrentUser = Depends(auth.get_current_admin)):
    """Clear users/problems/submissions/logs, re-create the initial admin,
    and log the caller out (api.md 测试支持)."""
    for d in (PROBLEMS_DIR, SUBMISSIONS_DIR, USERS_DIR, JUDGE_LOGS_DIR, ACCESS_LOGS_DIR):
        for p in d.glob("*.json"):
            p.unlink(missing_ok=True)
    submission_ops.reset_rate_limits()
    await log_ops.reset_visibility()
    language_ops.LANG_FILE.unlink(missing_ok=True)  # drop stray registrations
    await user_ops.ensure_initial_admin()
    await language_ops.ensure_builtins()
    request.session.clear()
    return {"code": 200, "msg": "system reset successfully", "data": None}
