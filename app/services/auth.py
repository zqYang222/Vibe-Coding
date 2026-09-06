"""Authentication helpers (Step 4).

Session-based login: after login the session stores the user id. On every
request `get_current_user` loads the authoritative user record from storage,
so role changes and bans take effect immediately.
"""

from fastapi import HTTPException, Request

from app.services import user_ops


class CurrentUser:
    """Lightweight view of the authenticated user."""

    def __init__(self, user_id: str, role: str):
        self.user_id = user_id
        self.role = role

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


async def get_current_user(request: Request) -> CurrentUser:
    """Resolve the logged-in user from the session; 401 if not logged in,
    403 if the account is banned."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="not logged in")
    user = await user_ops.get(str(user_id))
    if user is None:
        raise HTTPException(status_code=401, detail="not logged in")
    if user.get("role") == "banned":
        raise HTTPException(status_code=403, detail="user is banned")
    return CurrentUser(str(user["user_id"]), str(user["role"]))


async def get_current_admin(request: Request) -> CurrentUser:
    """Resolve the logged-in user and require the admin role; 403 otherwise."""
    user = await get_current_user(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="permission denied")
    return user
