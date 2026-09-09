"""
P0-RC-04：原文与 taskId 绑定；H5 不持久化全文；失败可按任务恢复。
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
H5 = ROOT / "frontend-h5" / "src"
sys.path.insert(0, str(ROOT / "backend-python"))

from fastapi.testclient import TestClient  # noqa: E402

from app.composition_root import get_analyze_text_use_case, get_task_store  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


def _read(*parts: str) -> str:
    return (H5.joinpath(*parts)).read_text(encoding="utf-8")


def _wait_done(client: TestClient, task_id: str, *, timeout_s: float = 8.0) -> dict:
    deadline = time.time() + timeout_s
    last = {}
    while time.time() < deadline:
        last = client.get(f"/api/v1/analyses/{task_id}").json()
        if last.get("task_status") in {"completed", "failed"}:
            return last
        time.sleep(0.1)
    raise AssertionError(f"task not done: {last}")


class SourceTextApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        get_settings.cache_clear()
        get_task_store.cache_clear()
        get_analyze_text_use_case.cache_clear()
        cls.client = TestClient(create_app())

    def test_two_tasks_source_text_do_not_cross(self):
        text_a = "任务A专属原文：结构性存款区间外收益可能为零。"
        text_b = "任务B专属原文：消费贷日利率与提前还款费用条款。"
        id_a = self.client.post("/api/v1/analyses", json={"text": text_a}).json()["task_id"]
        id_b = self.client.post("/api/v1/analyses", json={"text": text_b}).json()["task_id"]
        body_a = self.client.get(f"/api/v1/analyses/{id_a}").json()
        body_b = self.client.get(f"/api/v1/analyses/{id_b}").json()
        self.assertEqual(body_a["source_text"], text_a)
        self.assertEqual(body_b["source_text"], text_b)
        self.assertNotEqual(body_a["source_text"], body_b["source_text"])

    def test_failed_task_source_text_recoverable_for_resubmit(self):
        text = "失败恢复原文：模拟模型超时后仍可按任务重提。"
        create = self.client.post(
            "/api/v1/analyses",
            json={"text": text, "demo_error": "model_timeout"},
        )
        self.assertEqual(create.status_code, 200)
        task_id = create.json()["task_id"]
        body = _wait_done(self.client, task_id)
        self.assertEqual(body["task_status"], "failed")
        self.assertEqual(body["source_text"], text)
        # 用任务响应原文重新提交，得到新任务
        again = self.client.post("/api/v1/analyses", json={"text": body["source_text"]})
        self.assertEqual(again.status_code, 200)
        new_id = again.json()["task_id"]
        self.assertNotEqual(new_id, task_id)
        recovered = self.client.get(f"/api/v1/analyses/{new_id}").json()
        self.assertEqual(recovered["source_text"], text)

    def test_completed_report_keeps_own_source_text(self):
        text = "完成态原文绑定：区间外收益可能为零，本金保障需以合同为准。"
        task_id = self.client.post("/api/v1/analyses", json={"text": text}).json()["task_id"]
        body = _wait_done(self.client, task_id)
        self.assertEqual(body["task_status"], "completed")
        self.assertIsNotNone(body.get("report"))
        self.assertEqual(body["source_text"], text)


class H5TaskBindingContractTests(unittest.TestCase):
    def test_report_uses_get_source_text_not_pinia_draft(self):
        src = _read("pages", "ReportPage.vue")
        self.assertIn("data.source_text", src)
        self.assertIn("sourceText.value = data.source_text", src)
        # 禁止用全局草稿冒充当前任务原文
        self.assertNotIn("store.draftText", src)
        self.assertIn("故意不使用 Pinia 草稿", src)

    def test_session_storage_does_not_persist_full_text(self):
        store = _read("stores", "task.js")
        self.assertIn("sessionStorage", store)
        self.assertIn("taskId", store)
        self.assertIn("productHint", store)
        self.assertIn("忽略 text", store)
        # sessionStorage.setItem 的 JSON 只含元数据，不含正文
        self.assertIn(
            "JSON.stringify({\n            taskId: this.taskId || '',\n            taskStatus: this.taskStatus || '',\n            productHint: this.productHint || 'auto',\n          })",
            store,
        )
        self.assertNotIn("text: this.draftText", store)
        self.assertNotIn("draftText: this.draftText", store)

    def test_error_route_binds_task_id_and_no_draft_fallback(self):
        router = _read("router", "index.js")
        self.assertIn("/error/:taskId?", router)
        error = _read("pages", "ErrorPage.vue")
        self.assertIn("props.taskId", error)
        self.assertIn("data.source_text", error)
        self.assertIn("禁止回退全局草稿", error)
        # 有 taskId 时不得回退 store.draftText
        branch = error.split("if (props.taskId)")[1].split("return")[0]
        self.assertNotIn("store.draftText", branch)

    def test_report_redirects_running_to_status(self):
        src = _read("pages", "ReportPage.vue")
        self.assertIn("queued", src)
        self.assertIn("running", src)
        self.assertIn("name: 'status'", src)
        self.assertIn("任务可能因服务重启而丢失", src)

    def test_status_poll_recovers_after_transient_failure(self):
        src = _read("pages", "StatusPage.vue")
        self.assertIn("setTimeout", src)
        self.assertNotIn("setInterval(poll", src)
        self.assertIn("networkFails", src)
        self.assertIn(">= 3", src)
        self.assertIn("重新查询当前任务", src)
        self.assertIn("manualRepoll", src)
        self.assertIn("active = false", src)
        # 失败跳转必须带 taskId
        self.assertIn("params: { taskId: props.taskId }", src)

    def test_report_shows_all_candidates_with_confidence_and_evidence(self):
        src = _read("pages", "ReportPage.vue")
        self.assertIn("product_candidates", src)
        self.assertIn("v-for=\"(c, idx) in report.product_candidates", src)
        self.assertIn("confidence", src)
        self.assertIn("evidence_quotes", src)
        self.assertIn("candidateLabel", src)

    def test_pending_questions_deduped(self):
        src = _read("pages", "ReportPage.vue")
        self.assertIn("pendingItems", src)
        self.assertIn("seen.has", src)

    def test_input_clear_clears_pinia_draft(self):
        src = _read("pages", "InputPage.vue")
        self.assertIn("onClear", src)
        self.assertIn("clearDraft", src)


if __name__ == "__main__":
    unittest.main()
