"""合并祖先修订链上的有效纠错快照（P2-RC-04）。"""
from __future__ import annotations

from app.domain.models.correction import CorrectionKind, CorrectionRecord
from app.domain.models.report import AnalysisTask
from app.domain.ports.protocols import TaskStore


def _fact_merge_key(rec: CorrectionRecord) -> str:
    if rec.kind != CorrectionKind.fact_value:
        return rec.kind.value
    if rec.fact_id:
        return f"fact:{rec.fact_id}"
    if rec.parameter_key is not None:
        return f"param:{rec.parameter_key.value}"
    return f"id:{rec.correction_id}"


def merge_effective_corrections(
    *,
    parent: AnalysisTask,
    new_records: list[CorrectionRecord],
    task_store: TaskStore,
) -> list[CorrectionRecord]:
    """从根到父收集各代 corrections，再叠加上本轮差量；同键 last-write-wins。"""
    chain: list[AnalysisTask] = []
    cursor: AnalysisTask | None = parent
    seen: set[str] = set()
    while cursor is not None and cursor.task_id not in seen:
        seen.add(cursor.task_id)
        chain.append(cursor)
        if not cursor.parent_task_id:
            break
        cursor = task_store.get(cursor.parent_task_id)

    chain.reverse()  # 根 → 父
    merged: dict[str, CorrectionRecord] = {}
    for task in chain:
        if task.revision is None:
            continue
        for rec in task.revision.corrections:
            merged[_fact_merge_key(rec)] = rec
    for rec in new_records:
        merged[_fact_merge_key(rec)] = rec
    return list(merged.values())
