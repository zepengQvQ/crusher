"""P2-09：纠错修订不覆盖父报告，且 user_asserted 不伪装 document_fact。"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))
os.environ.setdefault("MOCK_MODE", "true")

from fastapi.testclient import TestClient  # noqa: E402

from app.application.analyze_text import AnalyzeTextUseCase  # noqa: E402
from app.application.reanalyze_with_correction import (  # noqa: E402
    CorrectionRejectedError,
    ReanalyzeWithCorrectionUseCase,
)
from app.config.settings import Settings  # noqa: E402
from app.domain.models import AnalyzeTextRequest  # noqa: E402
from app.domain.models.correction import CorrectionItem, CorrectionKind, CorrectionRequest  # noqa: E402
from app.domain.models.enums import FactStatus, ParameterKey  # noqa: E402
from app.domain.models.llm import LlmAnalysisDraft, LlmExplainRequest, draft_from_request  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402
from app.infrastructure.task_store.memory import InMemoryTaskStore  # noqa: E402
from app.main import create_app  # noqa: E402
from app.shared.enums import TaskStatus  # noqa: E402

PREPAY = (
    "本贷款支持提前还款，但需支付本金3%的违约金，逾期将计收高额罚息。"
    "借款金额为100000元。"
)


def _settings() -> Settings:
    return Settings(mock_mode=True, llm_api_key="test", llm_base_url="http://x")


class Gw:
    async def complete(self, request: LlmExplainRequest) -> LlmAnalysisDraft:
        return draft_from_request(
            request,
            "不能说没有风险：提前还款会产生3%的违约金。",
        )


class CorrectionRevisionTests(unittest.TestCase):
    def _parent_completed(self):
        store = InMemoryTaskStore()
        analyze = AnalyzeTextUseCase(
            task_store=store,
            knowledge_repository=LocalFileKnowledgeRepository(),
            llm_gateway=Gw(),
            settings=_settings(),
        )
        uc = ReanalyzeWithCorrectionUseCase(task_store=store, analyze_text=analyze)
        req = AnalyzeTextRequest(text=PREPAY, product_hint="loan")

        async def go():
            parent = analyze.submit(req)
            await analyze.run(parent.task_id, req)
            return store, analyze, uc, store.get(parent.task_id)

        return asyncio.run(go())

    def test_correction_keeps_parent_report(self) -> None:
        store, analyze, uc, parent = self._parent_completed()
        self.assertEqual(parent.task_status, TaskStatus.completed)
        parent_report = parent.report.model_dump()
        parent_id = parent.task_id

        param = next(p for p in parent.report.key_parameters if p.key == ParameterKey.amount)
        child = uc.submit(
            parent_id,
            CorrectionRequest(
                corrections=[
                    CorrectionItem(
                        kind=CorrectionKind.fact_value,
                        parameter_key=ParameterKey.amount,
                        corrected_value="200000",
                        previous_value=param.value,
                    )
                ]
            ),
        )

        async def run_child():
            await uc.run(child.task_id)
            return store.get(child.task_id), store.get(parent_id)

        child_done, parent_again = asyncio.run(run_child())
        self.assertEqual(parent_again.report.model_dump(), parent_report)
        self.assertEqual(child_done.parent_task_id, parent_id)
        self.assertIsNotNone(child_done.revision)
        self.assertEqual(child_done.revision.parent_task_id, parent_id)
        self.assertEqual(child_done.revision.revision_no, 1)
        amount = next(
            p for p in child_done.report.key_parameters if p.key == ParameterKey.amount
        )
        self.assertEqual(amount.status, FactStatus.user_asserted)
        self.assertEqual(amount.value, "200000")
        self.assertNotEqual(amount.status, FactStatus.document_fact)

    def test_unknown_parameter_rejected(self) -> None:
        _, _, uc, parent = self._parent_completed()
        with self.assertRaises(CorrectionRejectedError) as ctx:
            uc.submit(
                parent.task_id,
                CorrectionRequest(
                    corrections=[
                        CorrectionItem(
                            kind=CorrectionKind.fact_value,
                            parameter_key=ParameterKey.expected_return,
                            corrected_value="9%",
                        )
                    ]
                ),
            )
        self.assertEqual(ctx.exception.error_code, "CORRECTION_UNKNOWN_FACT")

    def test_http_correction_creates_new_task(self) -> None:
        app = create_app()
        client = TestClient(app)
        create = client.post(
            "/api/v1/analyses",
            json={"text": PREPAY, "product_hint": "loan", "locale": "zh-CN"},
        )
        self.assertEqual(create.status_code, 200)
        parent_id = create.json()["task_id"]
        body = None
        for _ in range(40):
            r = client.get(f"/api/v1/analyses/{parent_id}")
            body = r.json()
            if body["task_status"] in {"completed", "failed"}:
                break
        self.assertEqual(body["task_status"], "completed")
        keys = [p["key"] for p in body["report"]["key_parameters"]]
        self.assertIn("amount", keys)

        bad = client.post(
            f"/api/v1/analyses/{parent_id}/corrections",
            json={
                "corrections": [
                    {
                        "kind": "fact_value",
                        "parameter_key": "expected_return",
                        "corrected_value": "1%",
                    }
                ]
            },
        )
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()["detail"]["error_code"], "CORRECTION_UNKNOWN_FACT")

        ok = client.post(
            f"/api/v1/analyses/{parent_id}/corrections",
            json={
                "corrections": [
                    {
                        "kind": "fact_value",
                        "parameter_key": "amount",
                        "corrected_value": "88888",
                    }
                ]
            },
        )
        self.assertEqual(ok.status_code, 200)
        child_id = ok.json()["task_id"]
        self.assertNotEqual(child_id, parent_id)
        child_body = None
        for _ in range(40):
            r = client.get(f"/api/v1/analyses/{child_id}")
            child_body = r.json()
            if child_body["task_status"] in {"completed", "failed"}:
                break
        self.assertEqual(child_body["task_status"], "completed")
        self.assertEqual(child_body["parent_task_id"], parent_id)
        self.assertEqual(child_body["revision"]["parent_task_id"], parent_id)
        amt = next(p for p in child_body["report"]["key_parameters"] if p["key"] == "amount")
        self.assertEqual(amt["status"], "user_asserted")
        self.assertEqual(amt["value"], "88888")

        parent_after = client.get(f"/api/v1/analyses/{parent_id}").json()
        parent_amt = next(
            p for p in parent_after["report"]["key_parameters"] if p["key"] == "amount"
        )
        self.assertNotEqual(parent_amt.get("value"), "88888")


if __name__ == "__main__":
    unittest.main()
