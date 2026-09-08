"""P0-04：强类型 Schema 校验。"""
from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.domain.models import (  # noqa: E402
    AnalysisReport,
    Evidence,
    FactStatus,
    Finding,
    FindingSeverity,
    KeyParameter,
    ParameterKey,
    PlainLanguage,
    ProductCandidate,
    ProductRiskGrade,
    ProductTypeId,
)
from app.shared.enums import StageStatus  # noqa: E402


class SchemaStrictTests(unittest.TestCase):
    def test_reject_extra_fields(self) -> None:
        with self.assertRaises(ValidationError):
            ProductCandidate(
                product_type_id=ProductTypeId.loan,
                product_type_name="借贷",
                confidence=0.9,
                evidence_quotes=[],
                unexpected=True,  # type: ignore[call-arg]
            )

    def test_invalid_severity_enum(self) -> None:
        with self.assertRaises(ValidationError):
            Finding(
                id="f1",
                title="x",
                finding_severity="超高",  # type: ignore[arg-type]
                explanation="说明",
                evidence=[
                    Evidence(quote="原文", start=0, end=2),
                ],
                rule_or_knowledge_id="r1",
                confidence=0.5,
            )

    def test_invalid_amount_not_silently_null(self) -> None:
        with self.assertRaises(ValidationError):
            KeyParameter(
                key=ParameterKey.amount,
                label="金额",
                value="很多钱",
                status=FactStatus.document_fact,
                amount="很多钱",
            )

    def test_amount_decimal_ok(self) -> None:
        p = KeyParameter(
            key=ParameterKey.amount,
            label="金额",
            value="1000.50",
            status=FactStatus.document_fact,
            amount="1000.50",
        )
        self.assertEqual(p.amount, Decimal("1000.50"))

    def test_not_disclosed_cannot_carry_value(self) -> None:
        with self.assertRaises(ValidationError):
            KeyParameter(
                key=ParameterKey.term,
                label="期限",
                value="90天",
                status=FactStatus.not_disclosed,
            )

    def test_finding_requires_evidence(self) -> None:
        with self.assertRaises(ValidationError):
            Finding(
                id="f1",
                title="无证据",
                finding_severity=FindingSeverity.low,
                explanation="说明",
                evidence=[],
                rule_or_knowledge_id="r1",
                confidence=0.1,
            )

    def test_report_separates_product_grade_and_finding_severity(self) -> None:
        report = AnalysisReport(
            product_candidates=[
                ProductCandidate(
                    product_type_id=ProductTypeId.structured_deposit,
                    product_type_name="结构性存款",
                    confidence=0.8,
                    evidence_quotes=["结构性存款"],
                )
            ],
            product_risk_grade=ProductRiskGrade(
                value="R2",
                status=FactStatus.document_fact,
                note="原文写明",
            ),
            plain_language=PlainLanguage(text="白话", status=StageStatus.success),
            key_parameters=[],
            findings=[
                Finding(
                    id="f1",
                    title="收益骤降",
                    finding_severity=FindingSeverity.high,
                    explanation="区间突破后收益下降",
                    evidence=[Evidence(quote="突破区间", start=1, end=5)],
                    rule_or_knowledge_id="low_floor_return",
                    confidence=0.9,
                )
            ],
            missing_disclosures=[],
            general_references=[],
            pending_questions=[],
        )
        self.assertEqual(report.product_risk_grade.value, "R2")
        self.assertEqual(report.findings[0].finding_severity, FindingSeverity.high)
        self.assertIn("不进行用户适当性评估", report.disclaimer)


if __name__ == "__main__":
    unittest.main()
