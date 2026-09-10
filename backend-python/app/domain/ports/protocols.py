"""领域端口（Protocol）。

Java 对照：interface。Domain/Application 只依赖这些抽象。
"""
import re
from typing import Protocol

from app.domain.models.knowledge import (
    ProductKnowledge,
    RiskPatternKnowledge,
    TermKnowledge,
)
from app.domain.models.llm import LlmAnalysisDraft, LlmExplainRequest
from app.domain.models.report import AnalysisTask


class TaskStore(Protocol):
    """内存或其它存储的任务读写接口。"""

    def create(self, task: AnalysisTask) -> AnalysisTask:
        ...

    def get(self, task_id: str) -> AnalysisTask | None:
        ...

    def save(self, task: AnalysisTask) -> AnalysisTask:
        ...


class KnowledgeRepository(Protocol):
    """知识库查询端口。主链路直接调用，不走 MCP。"""

    def ping(self) -> bool:
        ...

    def list_products(self) -> list[ProductKnowledge]:
        ...

    def list_risk_patterns(self) -> list[RiskPatternKnowledge]:
        ...

    def list_terms(self) -> list[TermKnowledge]:
        ...

    def get_compiled_regex(self, pattern: str) -> re.Pattern[str]:
        ...


class LlmGateway(Protocol):
    """大模型网关端口。Demo 可用 Mock；确定性规则不经过此端口。"""

    async def complete(self, request: LlmExplainRequest) -> LlmAnalysisDraft:
        ...
