"""领域端口（Protocol）。

Java 对照：interface。Domain/Application 只依赖这些抽象。
"""
from typing import Optional, Protocol

from app.domain.models.task import AnalysisTask


class TaskStore(Protocol):
    """内存或其它存储的任务读写接口。"""

    def create(self, task: AnalysisTask) -> AnalysisTask:
        ...

    def get(self, task_id: str) -> Optional[AnalysisTask]:
        ...

    def save(self, task: AnalysisTask) -> AnalysisTask:
        ...


class KnowledgeRepository(Protocol):
    """知识库查询端口。P0-02 仅占位，内部主链路不走 MCP。"""

    def ping(self) -> bool:
        ...


class LlmGateway(Protocol):
    """大模型网关端口。P0-02 骨架使用 Mock，不真实调用。"""

    async def complete(self, prompt: str) -> str:
        ...
