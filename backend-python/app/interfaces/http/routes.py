"""HTTP 接口：请求/响应与 OpenAPI 同源。

Java 对照：@RestController + 全局校验异常映射。
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from app.application.analyze_text import AnalyzeTextUseCase
from app.composition_root import get_analyze_text_use_case, get_task_store
from app.config.settings import Settings, get_settings
from app.domain.models import AnalysisReport, CreateAnalysisRequest, StageInfo
from app.infrastructure.task_store.memory import InMemoryTaskStore
from app.shared.enums import ErrorCode, TaskStatus, user_message_for
from app.shared.logging_utils import log_task

router = APIRouter()

FORBIDDEN_CLIENT_FIELDS = frozenset(
    {
        "api_key",
        "llm_api_key",
        "base_url",
        "llm_base_url",
        "authorization",
        "token",
        "secret",
    }
)

SettingsDep = Annotated[Settings, Depends(get_settings)]
UseCaseDep = Annotated[AnalyzeTextUseCase, Depends(get_analyze_text_use_case)]
StoreDep = Annotated[InMemoryTaskStore, Depends(get_task_store)]


class CreateAnalysisResponse(BaseModel):
    """创建分析任务的响应。"""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_status: TaskStatus


class TaskResponse(BaseModel):
    """查询任务状态/报告的响应（含任务绑定原文）。"""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_status: TaskStatus
    created_at: datetime
    updated_at: datetime
    stages: list[StageInfo]
    error_code: ErrorCode | None = None
    error_message: str | None = None
    report: AnalysisReport | None = None
    is_failure: bool = False
    source_text: str = ""


def _forbidden_fields_from_validation(
    errors: list[dict[str, object]],
) -> list[str]:
    hit: set[str] = set()
    for err in errors:
        loc = err.get("loc") or ()
        if not isinstance(loc, (list, tuple)):
            continue
        for part in loc:
            if not isinstance(part, str):
                continue
            key = part.lower()
            if key in FORBIDDEN_CLIENT_FIELDS:
                hit.add(key)
        if err.get("type") == "extra_forbidden":
            for part in loc:
                if isinstance(part, str) and part.lower() in FORBIDDEN_CLIENT_FIELDS:
                    hit.add(part.lower())
    return sorted(hit)


async def request_validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """把非法请求映射成稳定 4xx，不把内部校验原文直接丢给 H5。

    Java 对照：@ControllerAdvice 统一包装 BindingResult。
    """
    del request  # 签名需与 FastAPI handler 一致
    if not isinstance(exc, RequestValidationError):
        raise exc
    raw_errors = exc.errors()
    errors: list[dict[str, object]] = [dict(e) for e in raw_errors]
    forbidden = _forbidden_fields_from_validation(errors)
    if forbidden:
        return JSONResponse(
            status_code=400,
            content={
                "detail": {
                    "error_code": ErrorCode.FORBIDDEN_CLIENT_CONFIG.value,
                    "message": user_message_for(ErrorCode.FORBIDDEN_CLIENT_CONFIG),
                    "fields": forbidden,
                }
            },
        )
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "error_code": "VALIDATION_ERROR",
                "message": "请求参数不合法",
            }
        },
    )


@router.get("/health")
def health(settings: SettingsDep) -> dict[str, object]:
    info = settings.public_info()
    info["status"] = "ok"
    return info


@router.post("/api/v1/analyses", response_model=CreateAnalysisResponse)
async def create_analysis(
    body: CreateAnalysisRequest,
    background_tasks: BackgroundTasks,
    use_case: UseCaseDep,
    settings: SettingsDep,
) -> CreateAnalysisResponse:
    """提交分析任务；真实模式下拒绝 demo_error。"""
    if body.demo_error is not None and not settings.mock_mode:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "DEMO_ERROR_NOT_ALLOWED",
                "message": "真实模式下不能使用 demo_error",
            },
        )

    if len(body.text) > settings.max_input_chars:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": ErrorCode.INPUT_TOO_LONG.value,
                "message": user_message_for(ErrorCode.INPUT_TOO_LONG),
                "max_input_chars": settings.max_input_chars,
            },
        )

    task = use_case.submit(body)
    background_tasks.add_task(use_case.run, task.task_id, body)
    return CreateAnalysisResponse(task_id=task.task_id, task_status=task.task_status)


@router.get("/api/v1/analyses/{task_id}", response_model=TaskResponse)
def get_analysis(task_id: str, store: StoreDep) -> TaskResponse:
    """按 task_id 查询状态与原文；失败任务不返回报告。"""
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
        source_text=task.source_text or "",
    )
