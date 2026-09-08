"""内存任务存储。

Java 对照：ConcurrentHashMap 实现的 TaskRepository。
Demo 仅单进程；重启后任务丢失可接受。
"""
from __future__ import annotations

from threading import Lock
from typing import Dict, Optional

from app.domain.models.task import AnalysisTask


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._tasks: Dict[str, AnalysisTask] = {}
        self._lock = Lock()

    def create(self, task: AnalysisTask) -> AnalysisTask:
        with self._lock:
            self._tasks[task.task_id] = task
            return task

    def get(self, task_id: str) -> Optional[AnalysisTask]:
        with self._lock:
            return self._tasks.get(task_id)

    def save(self, task: AnalysisTask) -> AnalysisTask:
        with self._lock:
            task.touch()
            self._tasks[task.task_id] = task
            return task
