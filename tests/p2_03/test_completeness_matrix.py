"""P2-03：各意图完整性矩阵（完整 / 缺失 / 冲突）。"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from fastapi.testclient import TestClient  # noqa: E402

from app.application.analysis_harness import AnalysisHarness  # noqa: E402
from app.application.check_input_completeness import CheckInputCompletenessUseCase  # noqa: E402
from app.domain.models.analysis_context import AnalysisContext, OutcomeStatus  # noqa: E402
from app.domain.models.completeness import (  # noqa: E402
    ClarificationAnswer,
    CompletenessCheckRequest,
)
from app.domain.models.enums import ProductHint  # noqa: E402
from app.domain.models.intent import IntentType, SourceEnvelope, SourceRole  # noqa: E402
from app.domain.models.llm import LlmExplainRequest, LlmAnalysisDraft, draft_from_request  # noqa: E402
from app.domain.models.p1_enums import CalculationKind, DayCountBasis  # noqa: E402
from app.domain.rules.engine import RuleEngine  # noqa: E402
from app.domain.rules.fact_extractor import FactExtractor  # noqa: E402
from app.domain.rules.product_resolver import ProductResolver  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402
from app.main import create_app  # noqa: E402


class CountingLlm:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, request: LlmExplainRequest) -> LlmAnalysisDraft:
        self.calls += 1
        return draft_from_request(request, "（测试）通俗说明")


class CompletenessMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.uc = CheckInputCompletenessUseCase()

    def test_single_complete(self) -> None:
        r = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.single_analysis,
                source_envelopes=[
                    SourceEnvelope(source_id="a", text="本贷款年化利率7.2%。")
                ],
                product_hint=ProductHint.loan,
            )
        )
        self.assertTrue(r.can_continue)
        self.assertEqual(r.questions, [])

    def test_single_missing_text(self) -> None:
        r = self.uc.execute(
            CompletenessCheckRequest(intent=IntentType.single_analysis, source_envelopes=[])
        )
        self.assertFalse(r.can_continue)
        self.assertTrue(r.questions)
        self.assertNotIn("source_envelopes", r.questions[0].prompt)

    def test_single_conflict_product_signals(self) -> None:
        text = "结构性存款观察区间已约定。另本合同为消费贷贷款，年化利率7.2%。"
        r = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.single_analysis,
                source_envelopes=[SourceEnvelope(source_id="a", text=text)],
                product_hint=ProductHint.auto,
            )
        )
        self.assertFalse(r.can_continue)
        self.assertEqual(r.questions[0].question_id, "product_type_confirm")
        self.assertIn("结构性存款还是贷款", r.questions[0].prompt)

    def test_dual_complete_and_missing(self) -> None:
        ok = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.dual_source_compare,
                source_envelopes=[
                    SourceEnvelope(
                        source_id="s",
                        role=SourceRole.sales_pitch,
                        text="销售：保证收益5%",
                    ),
                    SourceEnvelope(
                        source_id="o",
                        role=SourceRole.official_document,
                        text="正式：预期收益不保证",
                    ),
                ],
            )
        )
        self.assertTrue(ok.can_continue)
        miss = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.dual_source_compare,
                source_envelopes=[
                    SourceEnvelope(source_id="s", text="只有一侧"),
                ],
            )
        )
        self.assertFalse(miss.can_continue)
        conflict = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.dual_source_compare,
                source_envelopes=[
                    SourceEnvelope(source_id="a", text="A"),
                    SourceEnvelope(source_id="b", text="B"),
                ],
            )
        )
        self.assertFalse(conflict.can_continue)
        self.assertEqual(conflict.questions[0].question_id, "dual_roles")

    def test_product_compare_matrix(self) -> None:
        miss = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.product_compare,
                source_envelopes=[SourceEnvelope(source_id="a", text="产品甲")],
            )
        )
        self.assertFalse(miss.can_continue)
        self.assertIn("第二款", miss.questions[0].prompt)
        conflict = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.product_compare,
                source_envelopes=[
                    SourceEnvelope(source_id="a", text="产品甲"),
                    SourceEnvelope(source_id="b", text="产品乙"),
                ],
            )
        )
        self.assertFalse(conflict.can_continue)
        ok = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.product_compare,
                source_envelopes=[
                    SourceEnvelope(source_id="a", text="产品甲"),
                    SourceEnvelope(source_id="b", text="产品乙"),
                ],
                clarification_answers=[
                    ClarificationAnswer(question_id="compare_ab", value="order_as_is")
                ],
            )
        )
        self.assertTrue(ok.can_continue)

    def test_calculation_matrix(self) -> None:
        miss = self.uc.execute(
            CompletenessCheckRequest(intent=IntentType.calculation)
        )
        self.assertFalse(miss.can_continue)
        self.assertEqual(miss.questions[0].question_id, "calc_kind")
        partial = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.calculation,
                calculation_kind=CalculationKind.simple_return,
                principal="100000",
            )
        )
        self.assertFalse(partial.can_continue)
        ids = {q.question_id for q in partial.questions}
        self.assertTrue({"annual_rate_percent", "days", "day_count_basis"} & ids)
        ok = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.calculation,
                calculation_kind=CalculationKind.simple_return,
                principal="100000",
                annual_rate_percent="3.65",
                days="90",
                day_count_basis=DayCountBasis.days_365,
                user_confirmed_calculation=True,
            )
        )
        self.assertTrue(ok.can_continue)

    def test_follow_up_and_document(self) -> None:
        fu = self.uc.execute(CompletenessCheckRequest(intent=IntentType.evidence_follow_up))
        self.assertFalse(fu.can_continue)
        doc = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.document_extract,
                document_file_names=["a.docx"],
            )
        )
        self.assertFalse(doc.can_continue)
        self.assertIn("PDF", doc.questions[0].prompt)
        doc_ok = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.document_extract,
                document_file_names=["a.pdf"],
                document_bytes_total=1000,
                document_page_count=2,
            )
        )
        self.assertTrue(doc_ok.can_continue)

    def test_max_three_questions(self) -> None:
        r = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.calculation,
                calculation_kind=CalculationKind.simple_return,
            )
        )
        self.assertLessEqual(len(r.questions), 3)

    def test_incomplete_harness_skips_llm(self) -> None:
        knowledge = LocalFileKnowledgeRepository()
        rules = RuleEngine(knowledge)
        llm = CountingLlm()
        harness = AnalysisHarness(
            knowledge_repository=knowledge,
            llm_gateway=llm,
            product_resolver=ProductResolver(rules),
            fact_extractor=FactExtractor(knowledge),
            rule_engine=rules,
        )
        text = "结构性存款观察区间已约定。另本合同为消费贷贷款，年化利率7.2%。"
        ctx = AnalysisContext(task_id="tsk_c", source_text=text, product_hint=ProductHint.auto)
        result = asyncio.run(harness.run(ctx))
        self.assertEqual(result.outcome, OutcomeStatus.clarify)
        self.assertEqual(llm.calls, 0)
        self.assertTrue(result.report and result.report.pending_questions)

    def test_http(self) -> None:
        client = TestClient(create_app())
        res = client.post(
            "/api/v1/completeness/check",
            json={
                "intent": "single_analysis",
                "source_envelopes": [],
            },
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertFalse(body["can_continue"])
        self.assertLessEqual(len(body["questions"]), 3)


if __name__ == "__main__":
    unittest.main()
