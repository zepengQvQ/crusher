"""P2-01：校验结果最小 DTO（真实门禁在后续编号）。

用途：为 Harness VERIFY 阶段提供稳定结构。
输入：是否可发布、问题列表、失败阶段。
输出：VerificationResult。
不变量：P2-01 仅兼容适配器，不可伪造成功掩盖上游失败。
失败方式：can_publish=false 时携带 issues / error_code。
"""
from __future__ import annotations

from pydantic import Field

from app.domain.models.report import StrictModel
from app.shared.enums import ErrorCode


class VerificationResult(StrictModel):
    """发布前校验结果骨架。"""

    can_publish: bool = True
    issues: list[str] = Field(default_factory=list)
    failed_stage: str | None = None
    error_code: ErrorCode | None = None
    adapter_note: str = (
        "P2-01 兼容适配器：尚未启用真实幻觉/条件校验（见 P2-07）"
    )
