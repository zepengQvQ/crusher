"""组合根：显式构造依赖。"""
from functools import lru_cache

from app.application.analyze_text import AnalyzeTextUseCase
from app.config.settings import get_settings
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository
from app.infrastructure.llm.mock_gateway import MockLlmGateway
from app.infrastructure.task_store.memory import InMemoryTaskStore


@lru_cache
def get_task_store() -> InMemoryTaskStore:
    return InMemoryTaskStore()


@lru_cache
def get_analyze_text_use_case() -> AnalyzeTextUseCase:
    return AnalyzeTextUseCase(
        task_store=get_task_store(),
        knowledge_repository=LocalFileKnowledgeRepository(),
        llm_gateway=MockLlmGateway(),
        settings=get_settings(),
    )
