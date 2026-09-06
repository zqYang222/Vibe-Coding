"""Shared helpers: raw JSON body parsing."""

import json
from typing import Any, Dict

from fastapi import HTTPException, Request


async def parse_body(request: Request) -> Dict[str, Any]:
    """Parse the raw JSON body ourselves; malformed bodies raise 400.

    api.md requires 400 instead of FastAPI's default 422 (see FAQ), and
    reading the raw body lets us keep full control over the error message.
    """
    body = await request.body()
    try:
        data = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid body: not valid JSON")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Invalid body: expected a JSON object")
    return data
