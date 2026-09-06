"""FastAPI application entry point for the Online Judge system.

All endpoints use the async interface (async def), per the assignment's
technical requirement.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.config import SESSION_SECRET
from app.routers import ai, auth, languages, logs, problems, submissions, system, users
from app.services import language_ops, user_ops


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-register built-in languages (python / cpp) and create the
    # initial admin account (admin / admintestpassword) on startup.
    await language_ops.ensure_builtins()
    await user_ops.ensure_initial_admin()
    yield


app = FastAPI(title="Online Judge", version="0.1.0", lifespan=lifespan)

# Session-based login (Step 4).
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Render every HTTPException as the uniform {code, msg, data} envelope
    with a matching HTTP status code (api.md)."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "msg": str(exc.detail), "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """api.md requires 400 instead of FastAPI's default 422 (see FAQ)."""
    return JSONResponse(
        status_code=400,
        content={"code": 400, "msg": "Request body has validation errors", "data": None},
    )


app.include_router(problems.router)
app.include_router(languages.router)
app.include_router(submissions.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(logs.router)
app.include_router(system.router)
app.include_router(ai.router)


@app.get("/")
async def root():
    """Health-check endpoint."""
    return {"code": 200, "msg": "success", "data": {"service": "oj"}}
