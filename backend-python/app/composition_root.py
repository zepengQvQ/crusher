"""组合根：显式构造依赖。"""
from functools import lru_cache

from app.application.analyze_dual_sources import AnalyzeDualSourcesUseCase
from app.application.analyze_text import AnalyzeTextUseCase
from app.application.answer_from_evidence import AnswerFromEvidenceUseCase
from app.application.calculate_scenario import CalculateScenarioUseCase
from app.application.compare_products import CompareProductsUseCase
from app.application.extract_document import ExtractDocumentUseCase
from app.application.resolve_intent import ResolveIntentUseCase
from app.config.settings import Settings, get_settings
from app.domain.llm_errors import LlmConfigError
from app.domain.ports.protocols import LlmGateway
from app.infrastructure.document.mock_ocr import MockOcrGateway
from app.infrastructure.document.pdf_image_parser import PdfImageDocumentParser
from app.infrastructure.document.unavailable_ocr import UnavailableOcrGateway
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository
from app.infrastructure.llm.mock_gateway import MockLlmGateway
from app.infrastructure.llm.openai_compatible_gateway import OpenAiCompatibleLlmGateway
from app.infrastructure.task_store.memory import InMemoryTaskStore


def require_real_llm_settings(settings: Settings) -> None:
    """真实模式缺配置时明确失败，禁止悄悄退回 Mock。"""
    missing: list[str] = []
    if not settings.llm_api_key.strip() or settings.llm_api_key.strip() == "sk-your-api-key-here":
        missing.append("LLM_API_KEY")
    if not settings.llm_base_url.strip():
        missing.append("LLM_BASE_URL")
    if not settings.llm_model.strip():
        missing.append("LLM_MODEL")
    if missing:
        raise LlmConfigError(f"真实模式缺少配置: {', '.join(missing)}")


def build_llm_gateway(settings: Settings) -> LlmGateway:
    if settings.mock_mode:
        return MockLlmGateway()
    require_real_llm_settings(settings)
    return OpenAiCompatibleLlmGateway(settings)


@lru_cache
def get_task_store() -> InMemoryTaskStore:
    return InMemoryTaskStore()


@lru_cache
def get_analyze_text_use_case() -> AnalyzeTextUseCase:
    settings = get_settings()
    return AnalyzeTextUseCase(
        task_store=get_task_store(),
        knowledge_repository=LocalFileKnowledgeRepository(),
        llm_gateway=build_llm_gateway(settings),
        settings=settings,
    )


@lru_cache
def get_analyze_dual_sources_use_case() -> AnalyzeDualSourcesUseCase:
    return AnalyzeDualSourcesUseCase()


@lru_cache
def get_extract_document_use_case() -> ExtractDocumentUseCase:
    settings = get_settings()
    ocr = MockOcrGateway() if settings.mock_mode else UnavailableOcrGateway()
    return ExtractDocumentUseCase(PdfImageDocumentParser(ocr))


@lru_cache
def get_answer_from_evidence_use_case() -> AnswerFromEvidenceUseCase:
    return AnswerFromEvidenceUseCase()


@lru_cache
def get_calculate_scenario_use_case() -> CalculateScenarioUseCase:
    return CalculateScenarioUseCase()


@lru_cache
def get_compare_products_use_case() -> CompareProductsUseCase:
    return CompareProductsUseCase(LocalFileKnowledgeRepository())


@lru_cache
def get_resolve_intent_use_case() -> ResolveIntentUseCase:
    return ResolveIntentUseCase()
