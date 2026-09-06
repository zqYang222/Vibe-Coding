"""User management endpoints (Step 4)."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.user import AdminCreatePayload, RegisterPayload, RoleUpdatePayload
from app.services import auth, user_ops
from app.services.auth import CurrentUser
from app.utils import parse_body

router = APIRouter(prefix="/api/users", tags=["users"])

_USERNAME_MIN, _USERNAME_MAX = 3, 40
_PASSWORD_MIN = 6


def _public_user(user: dict) -> dict:
    """User info without the password hash."""
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "join_time": user.get("join_time", ""),
        "role": user.get("role", "user"),
        "submit_count": int(user.get("submit_count", 0)),
        "resolve_count": int(user.get("resolve_count", 0)),
    }


def _validate_credentials(username: str, password: str) -> None:
    if not (_USERNAME_MIN <= len(username) <= _USERNAME_MAX):
        raise HTTPException(
            status_code=400,
            detail=f"username length must be {_USERNAME_MIN}-{_USERNAME_MAX}",
        )
    if len(password) < _PASSWORD_MIN:
        raise HTTPException(
            status_code=400, detail=f"password must be at least {_PASSWORD_MIN} characters"
        )


@router.post("/admin")
async def create_admin(
    request: Request, _: CurrentUser = Depends(auth.get_current_admin)
):
    data = await parse_body(request)
    try:
        payload = AdminCreatePayload(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid body: {e}")
    _validate_credentials(payload.username, payload.password)
    if await user_ops.exists_username(payload.username):
        raise HTTPException(status_code=400, detail="username already exists")
    user = await user_ops.create(payload.username, payload.password, role="admin")
    return {
        "code": 200,
        "msg": "success",
        "data": {"user_id": user["user_id"], "username": user["username"]},
    }


@router.post("")
async def register(request: Request):
    data = await parse_body(request)
    try:
        payload = RegisterPayload(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid body: {e}")
    _validate_credentials(payload.username, payload.password)
    if await user_ops.exists_username(payload.username):
        raise HTTPException(status_code=400, detail="username already exists")
    user = await user_ops.create(payload.username, payload.password, role="user")
    return {
        "code": 200,
        "msg": "register success",
        "data": {
            "user_id": user["user_id"],
            "username": user["username"],
            "join_time": user["join_time"],
            "role": "user",
            "submit_count": 0,
            "resolve_count": 0,
        },
    }


@router.get("")
async def list_users(
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    _: CurrentUser = Depends(auth.get_current_admin),
):
    # Same pagination rules as GET /api/submissions/.
    if page is not None and page_size is None:
        raise HTTPException(status_code=400, detail="page_size is required when page is given")
    if page is not None and page < 1:
        raise HTTPException(status_code=400, detail="page must be >= 1")
    if page_size is not None and page_size < 1:
        raise HTTPException(status_code=400, detail="page_size must be >= 1")

    users = await user_ops.list_all()
    if page is None and page_size is None:
        items = users
    else:
        p = page if page is not None else 1
        start = (p - 1) * page_size
        items = users[start : start + page_size]

    return {
        "code": 200,
        "msg": "success",
        "data": {"total": len(users), "users": [_public_user(u) for u in items]},
    }


@router.get("/{user_id}")
async def get_user(
    user_id: str, current_user: CurrentUser = Depends(auth.get_current_user)
):
    user = await user_ops.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    if not current_user.is_admin and user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="permission denied")
    return {"code": 200, "msg": "success", "data": _public_user(user)}


@router.put("/{user_id}/role")
async def change_role(
    user_id: str,
    request: Request,
    current_user: CurrentUser = Depends(auth.get_current_admin),
):
    data = await parse_body(request)
    try:
        payload = RoleUpdatePayload(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid body: {e}")
    if payload.role not in user_ops.VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid body: invalid role")
    if await user_ops.get(user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    await user_ops.update_role(user_id, payload.role)
    # Step 4: record who changed whose role and when.
    await user_ops.log_admin_op(current_user.user_id, user_id, payload.role)
    return {
        "code": 200,
        "msg": "role updated",
        "data": {"user_id": user_id, "role": payload.role},
    }
