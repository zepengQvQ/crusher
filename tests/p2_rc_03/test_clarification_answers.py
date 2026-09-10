"""P2-RC-03：完整性追问答案校验与应用（F-04～F-07）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from fastapi.testclient import TestClient  # noqa: E402

from app.application.check_input_completeness import (  # noqa: E402
    CheckInputCompletenessUseCase,
    ClarificationRejected,
)
from app.domain.models.completeness import (  # noqa: E402
    ClarificationAnswer,
    CompletenessCheckRequest,
)
from app.domain.models.enums import ProductHint  # noqa: E402
from app.domain.models.intent import IntentType, SourceEnvelope, SourceRole  # noqa: E402
from app.domain.models.p1_enums import CalculationKind  # noqa: E402
from app.main import create_app  # noqa: E402

CONFLICT_TEXT = "结构性存款观察区间已约定。另本合同为消费贷贷款，年化利率7.2%。"


class ClarificationValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.uc = CheckInputCompletenessUseCase()

    def test_f04_product_type_banana_rejected(self) -> None:
        with self.assertRaises(ClarificationRejected):
            self.uc.execute(
                CompletenessCheckRequest(
                    intent=IntentType.single_analysis,
                    source_envelopes=[SourceEnvelope(source_id="a", text=CONFLICT_TEXT)],
                    product_hint=ProductHint.auto,
                    clarification_answers=[
                        ClarificationAnswer(
                            question_id="product_type_confirm", value="banana"
                        )
                    ],
                )
            )

    def test_f05_doc_missing_ok_cannot_continue(self) -> None:
        r = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.document_extract,
                document_file_names=[],
                clarification_answers=[
                    ClarificationAnswer(question_id="doc_missing", value="ok")
                ],
            )
        )
        self.assertFalse(r.can_continue)
        self.assertEqual(r.questions[0].question_id, "doc_missing")

    def test_f06_invalid_numeric_and_enum_rejected(self) -> None:
        for qid, value in (
            ("principal", "abc"),
            ("days", "-1"),
            ("day_count_basis", "banana"),
        ):
            with self.subTest(qid=qid, value=value):
                with self.assertRaises(ClarificationRejected):
                    self.uc.execute(
                        CompletenessCheckRequest(
                            intent=IntentType.calculation,
                            calculation_kind=CalculationKind.simple_return,
                            clarification_answers=[
                                ClarificationAnswer(question_id=qid, value=value)
                            ],
                        )
                    )

    def test_f07_illegal_calc_kind_not_500(self) -> None:
        client = TestClient(create_app())
        res = client.post(
            "/api/v1/completeness/check",
            json={
                "intent": "calculation",
                "clarification_answers": [
                    {"question_id": "calc_kind", "value": "not_a_kind"}
                ],
            },
        )
        self.assertEqual(res.status_code, 422)
        body = res.json()
        detail = body.get("detail") or body.get("error") or body
        if isinstance(detail, dict):
            code = detail.get("error_code")
        else:
            code = None
        self.assertEqual(code, "CLARIFICATION_INVALID")

    def test_compare_ab_swap_applies(self) -> None:
        a = SourceEnvelope(source_id="a", role=SourceRole.unknown, text="产品A材料期限12个月")
        b = SourceEnvelope(source_id="b", role=SourceRole.unknown, text="产品B材料期限6个月")
        r = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.product_compare,
                source_envelopes=[a, b],
                clarification_answers=[
                    ClarificationAnswer(question_id="compare_ab", value="swap")
                ],
            )
        )
        self.assertTrue(r.can_continue)
        assert r.resolved_request is not None
        self.assertEqual(r.resolved_request.source_envelopes[0].source_id, "b")
        self.assertEqual(r.resolved_request.source_envelopes[1].source_id, "a")

    def test_dual_roles_applied(self) -> None:
        r = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.dual_source_compare,
                source_envelopes=[
                    SourceEnvelope(source_id="s1", role=SourceRole.unknown, text="销售称收益5%"),
                    SourceEnvelope(source_id="s2", role=SourceRole.unknown, text="正式材料收益3%"),
                ],
                clarification_answers=[
                    ClarificationAnswer(question_id="dual_roles", value="second_official")
                ],
            )
        )
        self.assertTrue(r.can_continue)
        assert r.resolved_request is not None
        roles = [e.role for e in r.resolved_request.source_envelopes[:2]]
        self.assertEqual(roles, [SourceRole.sales_pitch, SourceRole.official_document])

    def test_unknown_and_duplicate_question_id(self) -> None:
        with self.assertRaises(ClarificationRejected):
            self.uc.execute(
                CompletenessCheckRequest(
                    intent=IntentType.single_analysis,
                    source_envelopes=[
                        SourceEnvelope(source_id="a", text="本贷款年化利率7.2%。")
                    ],
                    clarification_answers=[
                        ClarificationAnswer(question_id="not_exist", value="x")
                    ],
                )
            )
        with self.assertRaises(ClarificationRejected):
            self.uc.execute(
                CompletenessCheckRequest(
                    intent=IntentType.calculation,
                    calculation_kind=CalculationKind.simple_return,
                    clarification_answers=[
                        ClarificationAnswer(question_id="principal", value="10000"),
                        ClarificationAnswer(question_id="principal", value="20000"),
                    ],
                )
            )

    def test_valid_product_confirm_continues(self) -> None:
        r = self.uc.execute(
            CompletenessCheckRequest(
                intent=IntentType.single_analysis,
                source_envelopes=[SourceEnvelope(source_id="a", text=CONFLICT_TEXT)],
                product_hint=ProductHint.auto,
                clarification_answers=[
                    ClarificationAnswer(question_id="product_type_confirm", value="loan")
                ],
            )
        )
        self.assertTrue(r.can_continue)
        assert r.resolved_request is not None
        self.assertEqual(r.resolved_request.product_hint, ProductHint.loan)
        self.assertEqual(r.answered[0].value, "loan")


if __name__ == "__main__":
    unittest.main()
