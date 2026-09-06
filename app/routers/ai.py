"""AI problem generation endpoints (Advance module, R1-R4)."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.ai import ModelConfigPayload, ProblemTaskCreate
from app.services import ai_ops, auth, problem_ops
from app.services.auth import CurrentUser
from app.utils import parse_body

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.put("/model-config")
async def set_model_config(
    request: Request, _: CurrentUser = Depends(auth.get_current_user)
):
    data = await parse_body(request)
    try:
        payload = ModelConfigPayload(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid body: {e}")
    await ai_ops.set_config(payload.model_dump())
    return {"code": 200, "msg": "model config updated", "data": await ai_ops.public_config()}


@router.post("/problem-tasks/")
async def create_problem_task(
    request: Request, current_user: CurrentUser = Depends(auth.get_current_user)
):
    data = await parse_body(request)
    try:
        payload = ProblemTaskCreate(**data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid body: {e}")
    if payload.problem_id and not await problem_ops.exists(payload.problem_id):
        raise HTTPException(status_code=404, detail="problem not found")
    task_id = await ai_ops.create_task(
        current_user.user_id, payload.requirement, payload.problem_id
    )
    ai_ops.start_task(task_id)
    return {
        "code": 200,
        "msg": "task created",
        "data": {"task_id": task_id, "status": "pending"},
    }


@router.get("/problem-tasks/{task_id}")
async def get_problem_task(
    task_id: str, current_user: CurrentUser = Depends(auth.get_current_user)
):
    record = await ai_ops.get_task(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="task not found")
    if not current_user.is_admin and record["user_id"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="permission denied")
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "task_id": record["task_id"],
            "status": record["status"],
            "progress": record["progress"],
            "result": record.get("result"),
            "usage": record.get("usage"),
        },
    }


@router.put("/problem-tasks/{task_id}/cancel")
async def cancel_problem_task(
    task_id: str, current_user: CurrentUser = Depends(auth.get_current_user)
):
    record = await ai_ops.get_task(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="task not found")
    if not current_user.is_admin and record["user_id"] != current_user.user_id:
        raise HTTPException(status_code=403, detail="permission denied")
    if record["status"] in ("completed", "cancelled", "failed"):
        raise HTTPException(status_code=409, detail="task already finished")
    # Mark cancelled first, then stop the background runner (R3: the
    # cancellation must actually terminate the task, not just the UI).
    record["status"] = "cancelled"
    record["progress"] = "任务已中断"
    await ai_ops.update_task(record)
    ai_ops.cancel_task(task_id)
    return {
        "code": 200,
        "msg": "task cancelled",
        "data": {"task_id": task_id, "status": "cancelled"},
    }
