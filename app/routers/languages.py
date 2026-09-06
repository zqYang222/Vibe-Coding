"""Language registration & listing endpoints (Step 2).

TA Q&A #6: registration only records how to compile/run code; it never
installs compilers.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.language import LanguageModel
from app.services import auth, language_ops
from app.services.auth import CurrentUser
from app.utils import parse_body

router = APIRouter(prefix="/api/languages", tags=["languages"])

_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_+\-]{1,32}$")


@router.post("")
async def register_language(
    request: Request, _: CurrentUser = Depends(auth.get_current_user)
):
    data = await parse_body(request)
    try:
        lang = LanguageModel(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid body: {e}")
    if not _NAME_PATTERN.match(lang.name):
        raise HTTPException(status_code=400, detail="Invalid body: invalid language name")
    if not lang.file_ext.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid body: file_ext must start with '.'")
    if not lang.run_cmd.strip():
        raise HTTPException(status_code=400, detail="Invalid body: run_cmd is required")
    await language_ops.register(lang)
    return {"code": 200, "msg": "language registered", "data": {"name": lang.name}}


@router.get("")
async def list_languages():
    names = await language_ops.list_names()
    return {"code": 200, "msg": "success", "data": {"name": names}}
