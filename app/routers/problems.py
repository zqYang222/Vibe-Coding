"""Problem management endpoints (Step 1).

TA Q&A rulings baked in:
- testcases are returned to every logged-in user (#3);
- editing (PUT) is allowed for any logged-in user, deletion (DELETE) is
  admin-only (#3);
- deleting a problem cascades to its submissions/logs and reverts user
  counters (#4, #8) -- implemented in services/problem_ops.py.

Error priority follows api.md: 401 > 403 > 400 > 429 > 409 > 404 > 500.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.problem import ProblemModel
from app.services import auth, problem_ops
from app.services.auth import CurrentUser
from app.utils import parse_body

router = APIRouter(prefix="/api/problems", tags=["problems"])


@router.get("")
async def list_problems(_: CurrentUser = Depends(auth.get_current_user)):
    items = await problem_ops.list_all()
    return {"code": 200, "msg": "success", "data": items}


@router.get("/{problem_id}")
async def get_problem(
    problem_id: str, _: CurrentUser = Depends(auth.get_current_user)
):
    data = await problem_ops.get(problem_id)
    if data is None:
        raise HTTPException(status_code=404, detail="problem not found")
    # Normalize through the model so missing optional fields get their
    # default values (str -> "", list -> []) as api.md requires.
    problem = ProblemModel(**data).model_dump()
    return {"code": 200, "msg": "success", "data": problem}


@router.post("")
async def add_problem(
    request: Request, _: CurrentUser = Depends(auth.get_current_user)
):
    data = await parse_body(request)
    try:
        problem = ProblemModel(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid body: {e}")
    if not problem_ops.valid_id(problem.id):
        raise HTTPException(
            status_code=400,
            detail="Invalid body: problem id must match [A-Za-z0-9_-]{1,64}",
        )
    if await problem_ops.exists(problem.id):
        raise HTTPException(status_code=409, detail="problem already exists")
    await problem_ops.save(problem)
    return {"code": 200, "msg": "add success", "data": {"id": problem.id}}


@router.put("/{problem_id}")
async def update_problem(
    problem_id: str,
    request: Request,
    _: CurrentUser = Depends(auth.get_current_user),
):
    data = await parse_body(request)
    try:
        problem = ProblemModel(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid body: {e}")
    if problem.id != problem_id:
        raise HTTPException(status_code=400, detail="Invalid body: id does not match path")
    if not await problem_ops.exists(problem_id):
        raise HTTPException(status_code=404, detail="problem not found")
    await problem_ops.save(problem)
    return {"code": 200, "msg": "update success", "data": {"id": problem.id}}


@router.delete("/{problem_id}")
async def delete_problem(
    problem_id: str, _: CurrentUser = Depends(auth.get_current_admin)
):
    if not await problem_ops.exists(problem_id):
        raise HTTPException(status_code=404, detail="problem not found")
    await problem_ops.delete(problem_id)
    return {"code": 200, "msg": "delete success", "data": {"id": problem_id}}
