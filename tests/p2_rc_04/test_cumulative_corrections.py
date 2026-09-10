"""P2-RC-04：累积纠错与事实一致性（F-09）。"""
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
from app.application.reanalyze_with_correction import (  # noqa: E402
    CorrectionRejectedError,
    ReanalyzeWithCorrectionUseCase,
)
from app.config.settings import Settings  # noqa: E402
from app.domain.models import AnalyzeTextRequest  # noqa: E402
from app.domain.models.correction import (  # noqa: E402
    CorrectionItem,
    CorrectionKind,
    CorrectionRequest,
)
from app.domain.models.enums import FactStatus, ParameterKey, ProductHint  # noqa: E402
from app.domain.models.financial_fact import FinancialFactStatus  # noqa: E402
from app.domain.models.llm import LlmAnalysisDraft, LlmExplainRequest, draft_from_request  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402
from app.infrastructure.task_store.memory import InMemoryTaskStore  # noqa: E402
from app.shared.enums import TaskStatus  # noqa: E402

LOAN = (
    "本贷款金额10万元，期限12个月，年化利率7.20%。"
    "逾期按罚息计收。提前还款需支付违约金。风险等级：R2。"
)


class Gw:
    async def complete(self, request: LlmExplainRequest) -> LlmAnalysisDraft:
        return draft_from_request(request, "通俗说明：请核对利率与费用条款。")


class CumulativeCorrectionTests(unittest.TestCase):
    def _bootstrap(self):
        store = InMemoryTaskStore()
        analyze = AnalyzeTextUseCase(
            task_store=store,
            knowledge_repository=LocalFileKnowledgeRepository(),
            llm_gateway=Gw(),
            settings=Settings(mock_mode=True, llm_api_key="t", llm_base_url="http://x"),
        )
        uc = ReanalyzeWithCorrectionUseCase(task_store=store, analyze_text=analyze)

        async def go():
            req = AnalyzeTextRequest(text=LOAN, product_hint=ProductHint.loan)
            parent = analyze.submit(req)
            await analyze.run(parent.task_id, req)
            return store, uc, store.get(parent.task_id)

        return asyncio.run(go())

    def test_f09_amount_then_term_both_effective(self) -> None:
        store, uc, parent = self._bootstrap()
        self.assertEqual(parent.task_status, TaskStatus.completed)
        parent_dump = parent.report.model_dump()

        child1 = uc.submit(
            parent.task_id,
            CorrectionRequest(
                corrections=[
                    CorrectionItem(
                        kind=CorrectionKind.fact_value,
                        parameter_key=ParameterKey.amount,
                        corrected_value="200000",
                    )
                ]
            ),
        )

        async def run1():
            await uc.run(child1.task_id)
            return store.get(child1.task_id)

        rev1 = asyncio.run(run1())
        self.assertEqual(store.get(parent.task_id).report.model_dump(), parent_dump)
        amount1 = next(
            p for p in rev1.report.key_parameters if p.key == ParameterKey.amount
        )
        self.assertEqual(amount1.value, "200000")
        self.assertEqual(amount1.status, FactStatus.user_asserted)

        child2 = uc.submit(
            rev1.task_id,
            CorrectionRequest(
                corrections=[
                    CorrectionItem(
                        kind=CorrectionKind.fact_value,
                        parameter_key=ParameterKey.term,
                        corrected_value="24个月",
                    )
                ]
            ),
        )

        async def run2():
            await uc.run(child2.task_id)
            return store.get(child2.task_id), store.get(rev1.task_id)

        rev2, rev1_again = asyncio.run(run2())
        self.assertEqual(rev1_again.report.model_dump(), rev1.report.model_dump())
        amount2 = next(
            p for p in rev2.report.key_parameters if p.key == ParameterKey.amount
        )
        term2 = next(p for p in rev2.report.key_parameters if p.key == ParameterKey.term)
        self.assertEqual(amount2.value, "200000")
        self.assertEqual(amount2.status, FactStatus.user_asserted)
        self.assertEqual(term2.value, "24个月")
        self.assertEqual(term2.status, FactStatus.user_asserted)
        self.assertGreaterEqual(len(rev2.revision.effective_corrections), 2)

    def test_forged_fact_id_rejected(self) -> None:
        _, uc, parent = self._bootstrap()
        with self.assertRaises(CorrectionRejectedError) as ctx:
            uc.submit(
                parent.task_id,
                CorrectionRequest(
                    corrections=[
                        CorrectionItem(
                            kind=CorrectionKind.fact_value,
                            fact_id="ff_not_from_this_task",
                            corrected_value="999",
                        )
                    ]
                ),
            )
        self.assertEqual(ctx.exception.error_code, "CORRECTION_UNKNOWN_FACT")

    def test_user_asserted_has_no_forged_evidence(self) -> None:
        store, uc, parent = self._bootstrap()
        amount_ff = next(
            f for f in parent.report.financial_facts if f.field_key == "amount"
        )
        child = uc.submit(
            parent.task_id,
            CorrectionRequest(
                corrections=[
                    CorrectionItem(
                        kind=CorrectionKind.fact_value,
                        fact_id=amount_ff.fact_id,
                        parameter_key=ParameterKey.amount,
                        corrected_value="150000",
                    )
                ]
            ),
        )

        async def run():
            await uc.run(child.task_id)
            return store.get(child.task_id)

        done = asyncio.run(run())
        user_facts = [
            f
            for f in done.report.financial_facts
            if f.status == FinancialFactStatus.USER_ASSERTED
        ]
        self.assertTrue(user_facts)
        for f in user_facts:
            self.assertEqual(f.evidence_refs, [])
            self.assertTrue(f.supersedes_fact_id)
        # 原 CONFIRMED 仍在账本中
        self.assertTrue(
            any(
                f.fact_id == amount_ff.fact_id
                and f.status == FinancialFactStatus.CONFIRMED
                for f in done.report.financial_facts
            )
        )

    def test_source_text_change_stales_old_fact_correction(self) -> None:
        store, uc, parent = self._bootstrap()
        child1 = uc.submit(
            parent.task_id,
            CorrectionRequest(
                corrections=[
                    CorrectionItem(
                        kind=CorrectionKind.fact_value,
                        parameter_key=ParameterKey.amount,
                        corrected_value="200000",
                    )
                ]
            ),
        )

        async def run1():
            await uc.run(child1.task_id)
            return store.get(child1.task_id)

        rev1 = asyncio.run(run1())
        with self.assertRaises(CorrectionRejectedError) as ctx:
            uc.submit(
                rev1.task_id,
                CorrectionRequest(
                    corrections=[
                        CorrectionItem(
                            kind=CorrectionKind.source_text,
                            corrected_text=LOAN + "补充说明一行。",
                        )
                    ]
                ),
            )
        self.assertEqual(ctx.exception.error_code, "CORRECTION_STALE")

    def test_product_type_change_stales_loan_only_field(self) -> None:
        store, uc, parent = self._bootstrap()
        child1 = uc.submit(
            parent.task_id,
            CorrectionRequest(
                corrections=[
                    CorrectionItem(
                        kind=CorrectionKind.fact_value,
                        parameter_key=ParameterKey.annual_interest_rate,
                        corrected_value="6.5%",
                    )
                ]
            ),
        )

        async def run1():
            await uc.run(child1.task_id)
            return store.get(child1.task_id)

        rev1 = asyncio.run(run1())
        with self.assertRaises(CorrectionRejectedError) as ctx:
            uc.submit(
                rev1.task_id,
                CorrectionRequest(
                    corrections=[
                        CorrectionItem(
                            kind=CorrectionKind.product_type,
                            product_type=ProductHint.structured_deposit,
                        )
                    ]
                ),
            )
        self.assertEqual(ctx.exception.error_code, "CORRECTION_STALE")


if __name__ == "__main__":
    unittest.main()
