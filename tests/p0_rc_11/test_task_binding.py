"""P0-RC-11：taskId / product_hint / 范围字段绑定。"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.application.analyze_text import AnalyzeTextUseCase  # noqa: E402
from app.config.settings import Settings  # noqa: E402
from app.domain.models import AnalyzeTextRequest  # noqa: E402
from app.domain.models.enums import AnalysisScope, ProductHint, ProductTypeId  # noqa: E402
from app.domain.models.llm import LlmExplainRequest, LlmAnalysisDraft, make_simple_draft  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402
from app.infrastructure.task_store.memory import InMemoryTaskStore  # noqa: E402
from app.interfaces.http.routes import TaskResponse  # noqa: E402
from app.shared.enums import TaskStatus  # noqa: E402


def _settings() -> Settings:
    return Settings(
        mock_mode=True,
        llm_api_key="sk-test",
        llm_base_url="https://example.test/v1",
        llm_model="deepseek-chat",
        cors_origins="http://localhost:5173",
        max_input_chars=8000,
    )


class FixedGw:
    async def complete(self, request: LlmExplainRequest) -> LlmAnalysisDraft:
        _ = request
        return make_simple_draft("（测试）通俗说明。", fact_ids=list(request.allowed_fact_ids[:1]), finding_ids=list(request.allowed_finding_ids[:1]), knowledge_ids=list(request.allowed_knowledge_ids[:1]))


class TaskBindingTests(unittest.TestCase):
    def _uc(self):
        store = InMemoryTaskStore()
        uc = AnalyzeTextUseCase(
            task_store=store,
            knowledge_repository=LocalFileKnowledgeRepository(),
            llm_gateway=FixedGw(),
            settings=_settings(),
        )
        return uc, store

    def _run(self, uc, store, text: str, hint: str):
        req = AnalyzeTextRequest(text=text, product_hint=hint)

        async def go():
            task = uc.submit(req)
            await uc.run(task.task_id, req)
            return store.get(task.task_id)

        return asyncio.run(go())

    def test_submit_persists_product_hint(self):
        uc, store = self._uc()
        req = AnalyzeTextRequest(text="本贷款年化利率7.2%。", product_hint="loan")
        task = uc.submit(req)
        saved = store.get(task.task_id)
        self.assertEqual(saved.product_hint, ProductHint.loan)
        self.assertEqual(saved.source_text, req.text)

    def test_two_tasks_hint_and_text_do_not_cross(self):
        uc, store = self._uc()
        a = self._run(
            uc,
            store,
            "本产品为结构性存款，观察区间未突破。",
            "structured_deposit",
        )
        b = self._run(
            uc,
            store,
            "本贷款提前还款需支付剩余本金3%的违约金。",
            "loan",
        )
        self.assertEqual(a.product_hint, ProductHint.structured_deposit)
        self.assertEqual(b.product_hint, ProductHint.loan)
        self.assertIn("结构性存款", a.source_text)
        self.assertIn("贷款", b.source_text)
        self.assertNotEqual(a.source_text, b.source_text)
        self.assertEqual(a.resolved_product_type, ProductTypeId.structured_deposit)
        self.assertEqual(b.resolved_product_type, ProductTypeId.loan)
        self.assertEqual(a.analysis_scope, AnalysisScope.supported)
        self.assertEqual(b.analysis_scope, AnalysisScope.supported)

    def test_failed_task_keeps_hint_for_retry(self):
        class BoomGw:
            async def complete(self, request: LlmExplainRequest) -> LlmAnalysisDraft:
                from app.domain.llm_errors import LlmTimeoutError

                raise LlmTimeoutError("timeout")

        store = InMemoryTaskStore()
        uc = AnalyzeTextUseCase(
            task_store=store,
            knowledge_repository=LocalFileKnowledgeRepository(),
            llm_gateway=BoomGw(),
            settings=_settings(),
        )
        task = self._run(
            uc,
            store,
            "本贷款借款期限90天，年化利率7.2%。",
            "loan",
        )
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertIsNone(task.report)
        self.assertEqual(task.product_hint, ProductHint.loan)
        self.assertEqual(task.source_text, "本贷款借款期限90天，年化利率7.2%。")
        self.assertEqual(task.analysis_scope, AnalysisScope.supported)

    def test_task_response_exposes_binding_fields(self):
        fields = set(TaskResponse.model_fields)
        for name in ("source_text", "product_hint", "resolved_product_type", "analysis_scope"):
            self.assertIn(name, fields)


class FrontendBindingContractTests(unittest.TestCase):
    def test_store_clears_legacy_draft_key(self):
        store = (ROOT / "frontend-h5" / "src" / "stores" / "task.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("crusher_draft", store)
        self.assertIn("removeItem", store)

    def test_error_page_uses_task_product_hint(self):
        page = (ROOT / "frontend-h5" / "src" / "pages" / "ErrorPage.vue").read_text(
            encoding="utf-8"
        )
        self.assertIn("data.product_hint", page)
        self.assertIn("active", page)
        self.assertIn("onUnmounted", page)

    def test_status_page_recovers_draft_from_get(self):
        page = (ROOT / "frontend-h5" / "src" / "pages" / "StatusPage.vue").read_text(
            encoding="utf-8"
        )
        self.assertIn("applyTaskBinding", page)
        self.assertIn("重新分析（保留输入）", page)
        self.assertIn("返回重新输入", page)

    def test_helpers_allow_shared_pinia(self):
        helpers = (ROOT / "frontend-h5" / "src" / "test" / "helpers.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("createSharedPinia", helpers)
        self.assertIn("pinia", helpers)


if __name__ == "__main__":
    unittest.main()
