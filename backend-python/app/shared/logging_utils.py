"""日志工具：只记任务号和长度，不打印整段原文/模型全文。"""
from __future__ import annotations

import logging

logger = logging.getLogger("crusher")


def setup_logging() -> None:
    root = logging.getLogger("crusher")
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")
    )
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def log_task(event: str, task_id: str, **fields: object) -> None:
    safe = {k: v for k, v in fields.items() if k not in {"text", "prompt", "response", "raw"}}
    logger.info("%s task_id=%s %s", event, task_id, safe)
