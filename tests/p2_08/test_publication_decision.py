"""P2-08：统一发布决策与拒答/部分结果收口。"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))
os.environ.setdefault("MOCK_MODE", "true")

from app.application.analyze_text import AnalyzeTextUseCase  # noqa: E402
from app.config.settings import Settings  # noqa: E402
from app.domain.models import AnalyzeTextRequest  # noqa: E402
from app.domain.models.llm import LlmAnalysisDraft, LlmExplainRequest  # noqa: E402
from app.domain.models.llm import draft_from_request  # noqa: E402
from app.domain.models.verification import PublicationOutcome  # noqa: E402
from app.domain.validation.publication_gate import (  # noqa: E402
    decide_clarify,
    decide_from_verification,
    decide_publish,
    decide_publish_partial,
    decide_refuse,
)
from app.domain.models.verification import VerificationResult  # noqa: E402
from app.infrastructure.knowledge.local_files import (  # noqa: E402
    LocalFileKnowledgeRepository,
)
from app.infrastructure.task_store.memory import InMemoryTaskStore  # noqa: E402
from app.shared.enums import ErrorCode, TaskStatus  # noqa: E402

PREPAY = (
    "本贷款支持提前还款，但需支付本金3%的违约金，逾期将计收高额罚息。"
)


def _settings() -> Settings:
    return Settings(mock_mode=True, llm_api_key="test", llm_base_url="http://x")


class PublicationDecisionFactoryTests(unittest.TestCase):
    def test_factories_cover_four_outcomes(self) -> None:
        self.assertEqual(decide_publish().outcome, PublicationOutcome.publish)
        self.assertEqual(
            decide_publish_partial(reason_code=ErrorCode.OUTPUT_VERIFICATION_FAILED).outcome,
            PublicationOutcome.publish_partial,
        )
        self.assertEqual(
            decide_clarify(
                reason_code=ErrorCode.INPUT_INCOMPLETE, user_reason="缺资料"
            ).outcome,
            PublicationOutcome.clarify,
        )
        self.assertEqual(
            decide_refuse(reason_code=ErrorCode.MODEL_TIMEOUT).outcome,
            PublicationOutcome.refuse,
        )

    def test_verification_maps_to_partial(self) -> None:
        v = VerificationResult(
            can_publish=False,
            issues=["advice"],
            error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
            failed_checks=["boundary"],
        )
        d = decide_from_verification(v)
        self.assertEqual(d.outcome, PublicationOutcome.publish_partial)
        self.assertEqual(d.reason_code, ErrorCode.OUTPUT_VERIFICATION_FAILED)
        self.assertTrue(d.next_steps)
        self.assertTrue(d.coverage.checked)
        self.assertIn("模型通俗解释（未通过校验）", d.coverage.not_checked)


class PipelinePublicationTests(unittest.TestCase):
    def test_verification_failure_publish_partial_keeps_findings(self) -> None:
        class Gw:
            async def complete(self, request: LlmExplainRequest) -> LlmAnalysisDraft:
                return draft_from_request(request, "更适合你，建议购买。")

        store = InMemoryTaskStore()
        uc = AnalyzeTextUseCase(
            task_store=store,
            knowledge_repository=LocalFileKnowledgeRepository(),
            llm_gateway=Gw(),
            settings=_settings(),
        )
        req = AnalyzeTextRequest(text=PREPAY, product_hint="loan")

        async def go():
            task = uc.submit(req)
            await uc.run(task.task_id, req)
            return store.get(task.task_id)

        task = asyncio.run(go())
        self.assertEqual(task.task_status, TaskStatus.completed)
        self.assertIsNotNone(task.report)
        self.assertTrue(task.report.findings)
        self.assertIsNotNone(task.publication)
        self.assertEqual(task.publication.outcome, PublicationOutcome.publish_partial)
        self.assertEqual(
            task.publication.reason_code, ErrorCode.OUTPUT_VERIFICATION_FAILED
        )
        self.assertIn("【部分结果】", task.report.plain_language.text)

    def test_happy_path_publish_has_coverage(self) -> None:
        class Gw:
            async def complete(self, request: LlmExplainRequest) -> LlmAnalysisDraft:
                return draft_from_request(
                    request,
                    "不能说没有风险：提前还款会产生3%的违约金。",
                )

        store = InMemoryTaskStore()
        uc = AnalyzeTextUseCase(
            task_store=store,
            knowledge_repository=LocalFileKnowledgeRepository(),
            llm_gateway=Gw(),
            settings=_settings(),
        )
        req = AnalyzeTextRequest(text=PREPAY, product_hint="loan")

        async def go():
            task = uc.submit(req)
            await uc.run(task.task_id, req)
            return store.get(task.task_id)

        task = asyncio.run(go())
        self.assertEqual(task.task_status, TaskStatus.completed)
        self.assertEqual(task.publication.outcome, PublicationOutcome.publish)
        self.assertTrue(task.publication.coverage.checked)

    def test_timeout_still_refuse(self) -> None:
        class Gw:
            async def complete(self, request: LlmExplainRequest) -> LlmAnalysisDraft:
                raise AssertionError("demo_error 应在调用模型前停止")

        req = AnalyzeTextRequest(
            text=PREPAY, product_hint="loan", demo_error="model_timeout"
        )
        store = InMemoryTaskStore()
        uc = AnalyzeTextUseCase(
            task_store=store,
            knowledge_repository=LocalFileKnowledgeRepository(),
            llm_gateway=Gw(),
            settings=_settings(),
        )

        async def go():
            task = uc.submit(req)
            await uc.run(task.task_id, req)
            return store.get(task.task_id)

        task = asyncio.run(go())
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertIsNone(task.report)
        self.assertEqual(task.publication.outcome, PublicationOutcome.refuse)
        self.assertEqual(task.error_code, ErrorCode.MODEL_TIMEOUT)
        self.assertTrue(task.publication.next_steps)


if __name__ == "__main__":
    unittest.main()
