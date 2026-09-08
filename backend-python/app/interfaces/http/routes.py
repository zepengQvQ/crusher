"""HTTP 接口（P0-04：响应使用强类型 Report）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.application.analyze_text import AnalyzeTextUseCase
from app.composition_root import get_analyze_text_use_case, get_task_store
from app.config.settings import Settings, get_settings
from app.domain.models import (
    AnalysisReport,
    AnalyzeTextRequest,
    DemoErrorKind,
    StageInfo,
)
from app.infrastructure.task_store.memory import InMemoryTaskStore
from app.shared.enums import ErrorCode, TaskStatus, user_message_for
from app.shared.logging_utils import log_task

router = APIRouter()

_FORBIDDEN_CLIENT_FIELDS = {
    "api_key",
    "llm_api_key",
    "base_url",
    "llm_base_url",
    "authorization",
    "token",
    "secret",
}


class CreateAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_status: TaskStatus


class TaskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_status: TaskStatus
    created_at: datetime
    updated_at: datetime
    stages: list[StageInfo]
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None
    report: Optional[AnalysisReport] = None
    is_failure: bool = False


class AnalyzeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1)
    product_hint: str = "auto"
    locale: str = "zh-CN"
    demo_error: Optional[DemoErrorKind] = None


def _reject_forbidden_keys(payload: dict[str, Any]) -> None:
    lower_keys = {str(k).lower() for k in payload.keys()}
    hit = lower_keys & _FORBIDDEN_CLIENT_FIELDS
    if hit:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": ErrorCode.FORBIDDEN_CLIENT_CONFIG.value,
                "message": user_message_for(ErrorCode.FORBIDDEN_CLIENT_CONFIG),
                "fields": sorted(hit),
            },
        )


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, object]:
    info = settings.public_info()
    info["status"] = "ok"
    return info


@router.post("/api/v1/analyses", response_model=CreateAnalysisResponse)
async def create_analysis(
    request: Request,
    background_tasks: BackgroundTasks,
    use_case: AnalyzeTextUseCase = Depends(get_analyze_text_use_case),
    settings: Settings = Depends(get_settings),
) -> CreateAnalysisResponse:
    raw = await request.json()
    if not isinstance(raw, dict):
        raise HTTPException(status_code=400, detail={"message": "请求体必须是 JSON 对象"})
    _reject_forbidden_keys(raw)

    try:
        body = AnalyzeBody.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail={"message": str(exc)}) from exc

    if len(body.text) > settings.max_input_chars:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": ErrorCode.INPUT_TOO_LONG.value,
                "message": user_message_for(ErrorCode.INPUT_TOO_LONG),
                "max_input_chars": settings.max_input_chars,
            },
        )

    analyze_req = AnalyzeTextRequest(
        text=body.text,
        product_hint=body.product_hint,
        locale=body.locale,
        demo_error=body.demo_error,
    )
    task = use_case.submit(analyze_req)
    background_tasks.add_task(use_case.run, task.task_id, analyze_req)
    return CreateAnalysisResponse(task_id=task.task_id, task_status=task.task_status)


@router.get("/api/v1/analyses/{task_id}", response_model=TaskResponse)
def get_analysis(
    task_id: str,
    store: InMemoryTaskStore = Depends(get_task_store),
) -> TaskResponse:
    task = store.get(task_id)
    if task is None:
        log_task("task_not_found", task_id)
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": ErrorCode.TASK_NOT_FOUND.value,
                "message": user_message_for(ErrorCode.TASK_NOT_FOUND),
            },
        )
    failed = task.task_status == TaskStatus.failed
    return TaskResponse(
        task_id=task.task_id,
        task_status=task.task_status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        stages=task.stages,
        error_code=task.error_code,
        error_message=task.error_message,
        report=None if failed else task.report,
        is_failure=failed,
    )
