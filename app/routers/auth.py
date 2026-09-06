"""Login / logout endpoints (Step 4)."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.user import LoginPayload
from app.services import auth, user_ops
from app.services.auth import CurrentUser
from app.utils import parse_body

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(request: Request):
    data = await parse_body(request)
    try:
        payload = LoginPayload(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid body: {e}")
    user = await user_ops.get_by_username(payload.username)
    if user is None or not user_ops.check_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="wrong username or password")
    if user["role"] == "banned":
        raise HTTPException(status_code=403, detail="user is banned")
    request.session["user_id"] = user["user_id"]
    return {
        "code": 200,
        "msg": "login success",
        "data": {
            "user_id": user["user_id"],
            "username": user["username"],
            "role": user["role"],
        },
    }


@router.post("/logout")
async def logout(request: Request, _: CurrentUser = Depends(auth.get_current_user)):
    request.session.clear()
    return {"code": 200, "msg": "logout success", "data": None}
