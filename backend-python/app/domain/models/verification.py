"""P2-08：发布决策与覆盖说明；P2-07 VerificationResult 仍在此模块。

PublicationDecision 只能由 publication_gate 工厂函数创建，HTTP 层不得自行拼拒答文案。
本模块不依赖 report.py，避免与 AnalysisReport 形成循环导入。
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.shared.enums import ErrorCode


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PublicationOutcome(str, Enum):
    """统一结果状态（对外稳定）。"""

    publish = "publish"
    publish_partial = "publish_partial"
    clarify = "clarify"
    refuse = "refuse"


class AnalysisCoverage(_Strict):
    """本次系统检查了什么 / 没有检查什么。"""

    checked: list[str] = Field(default_factory=list)
    not_checked: list[str] = Field(default_factory=list)


class PublicationDecision(_Strict):
    """最终发布决策（领域层唯一真相）。"""

    outcome: PublicationOutcome
    reason_code: ErrorCode | None = None
    user_reason: str = Field(..., min_length=1)
    next_steps: list[str] = Field(default_factory=list)
    coverage: AnalysisCoverage = Field(default_factory=AnalysisCoverage)


class VerificationResult(_Strict):
    """发布前校验结果（P2-07）。"""

    can_publish: bool = True
    issues: list[str] = Field(default_factory=list)
    failed_stage: str | None = None
    error_code: ErrorCode | None = None
    adapter_note: str = ""
    failed_checks: list[str] = Field(default_factory=list)
