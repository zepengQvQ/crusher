"""P2-07：校验结果 DTO。

用途：为 Harness VERIFY 阶段提供稳定结构。
输入：是否可发布、问题列表、失败检查项。
输出：VerificationResult。
失败方式：can_publish=false 时携带 issues / error_code。
"""
from __future__ import annotations

from pydantic import Field

from app.domain.models.report import StrictModel
from app.shared.enums import ErrorCode


class VerificationResult(StrictModel):
    """发布前校验结果。"""

    can_publish: bool = True
    issues: list[str] = Field(default_factory=list)
    failed_stage: str | None = None
    error_code: ErrorCode | None = None
    adapter_note: str = ""
    failed_checks: list[str] = Field(default_factory=list)
