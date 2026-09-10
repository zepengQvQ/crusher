"""输入完整性检查用例（P2-03 / P2-RC-03）。

用途：对外检查某意图下输入是否可继续。
输入：CompletenessCheckRequest。
输出：CompletenessResult（含规范化答案与 resolved_request）。
不变量：不调用 LLM；最多 3 条追问。
失败方式：can_continue=false；非法澄清 → ClarificationRejected。
"""
from __future__ import annotations

from app.domain.models.completeness import CompletenessCheckRequest, CompletenessResult
from app.domain.rules.clarification_catalog import ClarificationRejected
from app.domain.rules.completeness_checker import CompletenessChecker


class CheckInputCompletenessUseCase:
    def __init__(self, checker: CompletenessChecker | None = None) -> None:
        self._checker = checker or CompletenessChecker()

    def execute(self, request: CompletenessCheckRequest) -> CompletenessResult:
        return self._checker.check(request)


__all__ = ["CheckInputCompletenessUseCase", "ClarificationRejected"]
