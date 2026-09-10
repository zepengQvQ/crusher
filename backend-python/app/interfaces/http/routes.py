"""HTTP 接口：请求/响应与 OpenAPI 同源。

Java 对照：@RestController + 全局校验异常映射。
"""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from app.application.analyze_dual_sources import AnalyzeDualSourcesUseCase
from app.application.analyze_text import AnalyzeTextUseCase
from app.application.answer_from_evidence import AnswerFromEvidenceUseCase
from app.application.calculate_scenario import CalculateScenarioUseCase
from app.application.compare_products import CompareProductsUseCase
from app.application.extract_document import ExtractDocumentUseCase
from app.application.resolve_intent import ResolveIntentUseCase
from app.composition_root import (
    get_analyze_dual_sources_use_case,
    get_analyze_text_use_case,
    get_answer_from_evidence_use_case,
    get_calculate_scenario_use_case,
    get_compare_products_use_case,
    get_extract_document_use_case,
    get_resolve_intent_use_case,
    get_task_store,
)
from app.config.settings import Settings, get_settings
from app.domain.models import (
    AnalysisReport,
    ApiErrorResponse,
    CreateAnalysisRequest,
    DualAnalysisReport,
    DualAnalysisRequest,
    StageInfo,
)
from app.domain.models.calculation import CalculateScenarioRequest, CalculationResult
from app.domain.models.enums import AnalysisScope, ProductHint, ProductTypeId
from app.domain.models.evidence_answer import EvidenceAnswer, FollowUpRequest
from app.domain.models.intent import IntentDecision, IntentResolveRequest
from app.domain.models.product_facts import ProductCompareRequest, ProductComparisonReport
from app.domain.models.source_document import ExtractedDocument
from app.infrastructure.task_store.memory import InMemoryTaskStore
from app.shared.constants import MAX_INPUT_CHARS
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
DualUseCaseDep = Annotated[
    AnalyzeDualSourcesUseCase, Depends(get_analyze_dual_sources_use_case)
]
ExtractUseCaseDep = Annotated[
    ExtractDocumentUseCase, Depends(get_extract_document_use_case)
]
FollowUpUseCaseDep = Annotated[
    AnswerFromEvidenceUseCase, Depends(get_answer_from_evidence_use_case)
]
CalculateUseCaseDep = Annotated[
    CalculateScenarioUseCase, Depends(get_calculate_scenario_use_case)
]
CompareUseCaseDep = Annotated[
    CompareProductsUseCase, Depends(get_compare_products_use_case)
]
IntentUseCaseDep = Annotated[ResolveIntentUseCase, Depends(get_resolve_intent_use_case)]
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
    product_hint: ProductHint = ProductHint.auto
    resolved_product_type: ProductTypeId | None = None
    analysis_scope: AnalysisScope | None = None


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
    if _is_text_too_long(errors):
        return JSONResponse(
            status_code=400,
            content={
                "detail": {
                    "error_code": ErrorCode.INPUT_TOO_LONG.value,
                    "message": user_message_for(ErrorCode.INPUT_TOO_LONG),
                    "max_input_chars": MAX_INPUT_CHARS,
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


def _is_text_too_long(errors: list[dict[str, object]]) -> bool:
    for err in errors:
        typ = str(err.get("type") or "")
        if typ not in {"string_too_long", "value_error.any_str.max_length"}:
            continue
        loc = err.get("loc") or ()
        if isinstance(loc, (list, tuple)) and any(
            name in loc for name in ("text", "sales_text", "official_text")
        ):
            return True
    return False


@router.get("/health")
def health(settings: SettingsDep) -> dict[str, object]:
    info = settings.public_info()
    info["status"] = "ok"
    return info


@router.post(
    "/api/v1/analyses",
    response_model=CreateAnalysisResponse,
    responses={
        400: {"model": ApiErrorResponse, "description": "业务拒绝或输入超长"},
        422: {"model": ApiErrorResponse, "description": "请求参数不合法"},
    },
)
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

    # 上限已由 CreateAnalysisRequest.max_length 契约校验；此处兜底与常量一致
    if len(body.text) > MAX_INPUT_CHARS:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": ErrorCode.INPUT_TOO_LONG.value,
                "message": user_message_for(ErrorCode.INPUT_TOO_LONG),
                "max_input_chars": MAX_INPUT_CHARS,
            },
        )

    task = use_case.submit(body)
    background_tasks.add_task(use_case.run, task.task_id, body)
    return CreateAnalysisResponse(task_id=task.task_id, task_status=task.task_status)


@router.get(
    "/api/v1/analyses/{task_id}",
    response_model=TaskResponse,
    responses={
        404: {"model": ApiErrorResponse, "description": "任务不存在"},
        422: {"model": ApiErrorResponse, "description": "请求参数不合法"},
    },
)
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
        product_hint=task.product_hint,
        resolved_product_type=task.resolved_product_type,
        analysis_scope=task.analysis_scope,
    )


@router.post(
    "/api/v1/dual-analyses",
    response_model=DualAnalysisReport,
    responses={
        400: {"model": ApiErrorResponse, "description": "材料不足或超长"},
        422: {"model": ApiErrorResponse, "description": "请求参数不合法"},
    },
)
def create_dual_analysis(
    body: DualAnalysisRequest,
    use_case: DualUseCaseDep,
) -> DualAnalysisReport:
    """销售话术 vs 正式材料对照（同步返回，不走任务轮询）。"""
    if not body.sales_text.strip() or not body.official_text.strip():
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": "请同时提供销售话术与正式材料，单边为空无法对照",
            },
        )
    return use_case.execute(body)


@router.post(
    "/api/v1/documents/extract",
    response_model=ExtractedDocument,
    responses={
        400: {"model": ApiErrorResponse, "description": "文件不合法或超限"},
        422: {"model": ApiErrorResponse, "description": "请求参数不合法"},
        503: {"model": ApiErrorResponse, "description": "OCR 不可用"},
    },
)
async def extract_document(
    use_case: ExtractUseCaseDep,
    files: Annotated[list[UploadFile], File(description="PDF 或图片，可多文件")],
) -> ExtractedDocument:
    """上传 PDF/图片并提取可编辑文本；用户确认后再进入金融分析。"""
    if not files:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": ErrorCode.DOCUMENT_PARSE_FAILED.value,
                "message": "请至少上传一个文件",
            },
        )
    payloads: list[tuple[str, bytes]] = []
    for f in files:
        name = f.filename or "upload.bin"
        data = await f.read()
        payloads.append((name, data))

    try:
        # 单 PDF：优先按 PDF 解析；多文件或图片走图片路径
        only = payloads[0]
        lower = only[0].lower()
        if len(payloads) == 1 and lower.endswith(".pdf"):
            result = await use_case.extract_pdf(only[1], only[0])
        else:
            if any(n.lower().endswith(".pdf") for n, _ in payloads):
                raise ValueError("请单独上传一个 PDF，或只上传图片")
            result = await use_case.extract_images(payloads)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": ErrorCode.DOCUMENT_PARSE_FAILED.value,
                "message": str(exc),
            },
        ) from exc

    if result.message == "OCR_UNAVAILABLE" or (
        result.overall_status.value == "failed"
        and any("OCR_UNAVAILABLE" in (p.error_message or "") for p in result.pages)
    ):
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": ErrorCode.OCR_UNAVAILABLE.value,
                "message": user_message_for(ErrorCode.OCR_UNAVAILABLE),
            },
        )
    return result


@router.post(
    "/api/v1/follow-ups",
    response_model=EvidenceAnswer,
    responses={
        400: {"model": ApiErrorResponse, "description": "问题或材料不合法"},
        422: {"model": ApiErrorResponse, "description": "请求参数不合法"},
    },
)
def create_follow_up(
    body: FollowUpRequest,
    use_case: FollowUpUseCaseDep,
) -> EvidenceAnswer:
    """基于已提交材料追问；无证据则 insufficient，超范围 out_of_scope。"""
    return use_case.execute(body)


@router.post(
    "/api/v1/calculations",
    response_model=CalculationResult,
    responses={
        400: {"model": ApiErrorResponse, "description": "计算参数不合法或未确认"},
        422: {"model": ApiErrorResponse, "description": "请求参数不合法"},
    },
)
def create_calculation(
    body: CalculateScenarioRequest,
    use_case: CalculateUseCaseDep,
) -> CalculationResult:
    """用户确认参数后的 Decimal 确定性计算；模型不参与算数。"""
    try:
        return use_case.execute(body)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": ErrorCode.CALCULATION_INVALID.value,
                "message": str(exc) or user_message_for(ErrorCode.CALCULATION_INVALID),
            },
        ) from exc


@router.post(
    "/api/v1/product-comparisons",
    response_model=ProductComparisonReport,
    responses={
        422: {"model": ApiErrorResponse, "description": "请求参数不合法"},
    },
)
def create_product_comparison(
    body: ProductCompareRequest,
    use_case: CompareUseCaseDep,
) -> ProductComparisonReport:
    """两款产品固定维度事实对照；不输出推荐或综合评分。"""
    return use_case.execute(body)


@router.post(
    "/api/v1/intents/resolve",
    response_model=IntentDecision,
    responses={
        422: {"model": ApiErrorResponse, "description": "请求参数不合法"},
    },
)
def resolve_intent(
    body: IntentResolveRequest,
    use_case: IntentUseCaseDep,
) -> IntentDecision:
    """识别用户意图；显式页面意图优先，材料正文指令无效。"""
    return use_case.execute(body)
