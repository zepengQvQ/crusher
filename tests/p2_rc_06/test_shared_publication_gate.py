"""P2-RC-06：双材料 / 产品对比 / 追问 / 计算共用结果门禁。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.application.analyze_dual_sources import AnalyzeDualSourcesUseCase  # noqa: E402
from app.application.answer_from_evidence import AnswerFromEvidenceUseCase  # noqa: E402
from app.application.calculate_scenario import CalculateScenarioUseCase  # noqa: E402
from app.application.compare_products import CompareProductsUseCase  # noqa: E402
from app.domain.models.calculation import CalculateScenarioRequest  # noqa: E402
from app.domain.models.claim_comparison import (  # noqa: E402
    Claim,
    ClaimComparison,
    DualAnalysisReport,
    DualAnalysisRequest,
    EvidenceRef,
    SourceDocument,
)
from app.domain.models.enums import ProductHint  # noqa: E402
from app.domain.models.evidence_answer import (  # noqa: E402
    AnswerStatus,
    EvidenceAnswer,
    FollowUpRequest,
)
from app.domain.models.p1_enums import (  # noqa: E402
    CalculationKind,
    ClaimStatus,
    ClaimSubject,
    DiffStatus,
    FieldStatus,
    ProductFactDimension,
    SourceType,
)
from app.domain.models.product_facts import (  # noqa: E402
    DimensionComparison,
    FactSideValue,
    ProductCompareRequest,
    ProductComparisonReport,
    ProductFacts,
)
from app.domain.models.verification import PublicationOutcome  # noqa: E402
from app.domain.validation.publication_service import (  # noqa: E402
    PublicationService,
    ResultGate,
)
from app.infrastructure.knowledge.local_files import (  # noqa: E402
    LocalFileKnowledgeRepository,
)

_ALLOWED = {
    PublicationOutcome.publish,
    PublicationOutcome.publish_partial,
    PublicationOutcome.clarify,
    PublicationOutcome.refuse,
}

AMOUNT_SRC = "本贷款金额10万元，期限12个月。年化利率7.2%。"


class FakeEvidenceBlockedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.gate = PublicationService()

    def test_dual_forged_official_evidence_downgraded(self) -> None:
        sales_text = "预期年化收益率5%。"
        official_text = "到期年化收益率3%。"
        sales = SourceDocument(
            source_type=SourceType.sales_pitch,
            name="销售",
            text=sales_text,
        )
        official = SourceDocument(
            source_type=SourceType.official_document,
            name="正式",
            text=official_text,
        )
        quote = "预期年化收益率5%"
        sales_ev = EvidenceRef(
            source_id=sales.source_id,
            quote=quote,
            start=sales_text.index(quote),
            end=sales_text.index(quote) + len(quote),
        )
        forged = EvidenceRef(
            source_id=official.source_id,
            quote="保本承诺",
            start=0,
            end=4,
        )
        raw = DualAnalysisReport(
            sales_source=sales,
            official_source=official,
            comparisons=[
                ClaimComparison(
                    comparison_id="cmp_fake",
                    subject=ClaimSubject.expected_return,
                    status=ClaimStatus.confirmed,
                    summary="假证据硬判一致",
                    sales_claim=Claim(
                        claim_id="clm1",
                        subject=ClaimSubject.expected_return,
                        summary="5%",
                        evidence=sales_ev,
                    ),
                    official_evidence=forged,
                )
            ],
        )
        out = self.gate.finalize_dual(raw)
        hit = out.comparisons[0]
        self.assertNotEqual(hit.status, ClaimStatus.confirmed)
        self.assertEqual(hit.status, ClaimStatus.uncertain)
        self.assertIsNotNone(out.publication)
        assert out.publication is not None
        self.assertIn(out.publication.outcome, _ALLOWED)
        self.assertNotEqual(out.publication.outcome, PublicationOutcome.publish)

    def test_compare_forged_side_evidence_blocked(self) -> None:
        text_a = "结构性存款，期限12个月。到期年化收益率3.5%。"
        text_b = "结构性存款，期限1年。到期年化收益率3.5%。"
        forged = EvidenceRef(
            source_id="prod_a",
            quote="保本无忧",
            start=0,
            end=4,
        )
        raw = ProductComparisonReport(
            product_a=ProductFacts(
                product_id="prod_a",
                label="A",
                product_type=None,
                source_text=text_a,
            ),
            product_b=ProductFacts(
                product_id="prod_b",
                label="B",
                product_type=None,
                source_text=text_b,
            ),
            dimensions=[
                DimensionComparison(
                    dimension=ProductFactDimension.term,
                    label="期限",
                    status=DiffStatus.same,
                    side_a=FactSideValue(
                        display="12个月",
                        normalized="12",
                        status=FieldStatus.confirmed,
                        evidence=[forged],
                    ),
                    side_b=FactSideValue(
                        display="1年",
                        normalized="12",
                        status=FieldStatus.confirmed,
                        evidence=[
                            EvidenceRef(
                                source_id="prod_b",
                                quote="1年",
                                start=text_b.index("1年"),
                                end=text_b.index("1年") + 2,
                            )
                        ],
                    ),
                    note="标准化后一致",
                )
            ],
        )
        out = self.gate.finalize_compare(raw)
        term = out.dimensions[0]
        self.assertNotEqual(term.side_a.status, FieldStatus.confirmed)
        self.assertNotEqual(term.status, DiffStatus.same)
        self.assertIsNotNone(out.publication)
        assert out.publication is not None
        self.assertIn(out.publication.outcome, _ALLOWED)

    def test_follow_up_forged_evidence_blocked(self) -> None:
        text = "本贷款年化利率7.2%。"
        forged = EvidenceAnswer(
            question="利率多少？",
            status=AnswerStatus.answered,
            answer="看起来有答案",
            evidence=[
                EvidenceRef(
                    source_id="source",
                    quote="保本承诺",
                    start=0,
                    end=4,
                )
            ],
        )
        out = self.gate.finalize_follow_up(forged, source_text=text)
        self.assertEqual(out.status, AnswerStatus.insufficient_evidence)
        self.assertFalse(out.evidence)
        self.assertIsNotNone(out.publication)
        assert out.publication is not None
        self.assertIn(out.publication.outcome, _ALLOWED)


class AmountEvidenceTests(unittest.TestCase):
    def test_product_compare_keeps_10wan_yuan_quote(self) -> None:
        other = "结构性存款产品，起购金额5万元，期限6个月。"
        uc = CompareProductsUseCase(LocalFileKnowledgeRepository())
        out = uc.execute(
            ProductCompareRequest(
                text_a=AMOUNT_SRC,
                text_b=other,
                product_hint_a=ProductHint.loan,
            )
        )
        amount = next(d for d in out.dimensions if d.dimension.value == "amount")
        blob = (amount.side_a.display or "") + "".join(
            e.quote for e in amount.side_a.evidence
        )
        self.assertIn("10万元", blob)
        self.assertIsNotNone(out.publication)
        assert out.publication is not None
        self.assertIn(out.publication.outcome, _ALLOWED)


class KeywordOnlyFollowUpTests(unittest.TestCase):
    def test_keyword_hit_without_answer_is_insufficient(self) -> None:
        text = "收益说明见附件，详情以合同为准。"
        ans = AnswerFromEvidenceUseCase().execute(
            FollowUpRequest(question="年化收益率是多少？", source_text=text)
        )
        self.assertEqual(ans.status, AnswerStatus.insufficient_evidence)
        self.assertIn("材料里只有相关字眼，还不足以给出确定结论", ans.answer)
        self.assertIsNotNone(ans.publication)
        assert ans.publication is not None
        self.assertIn(ans.publication.outcome, _ALLOWED)


class ExternalOutcomeTests(unittest.TestCase):
    def test_all_entry_outcomes_are_allowed(self) -> None:
        dual = AnalyzeDualSourcesUseCase().execute(
            DualAnalysisRequest(
                sales_text="预期年化收益率5%。",
                official_text="到期年化收益率5%。",
            )
        )
        compare = CompareProductsUseCase(LocalFileKnowledgeRepository()).execute(
            ProductCompareRequest(
                text_a="结构性存款，期限12个月。到期年化收益率3.5%。",
                text_b="结构性存款，期限1年。到期年化收益率2.0%-4.0%。",
            )
        )
        follow = AnswerFromEvidenceUseCase().execute(
            FollowUpRequest(
                question="年化利率多少？",
                source_text="本贷款年化利率7.2%。提前还款需支付违约金。",
            )
        )
        calc = CalculateScenarioUseCase().execute(
            CalculateScenarioRequest(
                kind=CalculationKind.simple_return,
                user_confirmed=True,
                principal="100000",
                annual_rate_percent="3.5",
                days="365",
            )
        )
        for pub in (
            dual.publication,
            compare.publication,
            follow.publication,
            calc.publication,
        ):
            self.assertIsNotNone(pub)
            assert pub is not None
            self.assertIn(pub.outcome, _ALLOWED)

        self.assertIs(ResultGate, PublicationService)
        self.assertTrue(calc.formula)
        self.assertTrue(calc.inputs)
        self.assertTrue(calc.rounding)
        self.assertTrue(calc.result)


if __name__ == "__main__":
    unittest.main()
