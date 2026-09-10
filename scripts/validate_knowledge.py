#!/usr/bin/env python3
"""校验本地 knowledge/ 契约，无需启动 H5。

用法（仓库根目录）:
  make validate-knowledge
  或: PYTHONPATH=backend-python backend-python/.venv/bin/python scripts/validate_knowledge.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend-python"
sys.path.insert(0, str(BACKEND))

from app.infrastructure.knowledge.schemas import (  # noqa: E402
    KnowledgeValidationError,
    validate_knowledge_dir,
)


def main() -> int:
    knowledge_dir = ROOT / "knowledge"
    try:
        bundle = validate_knowledge_dir(knowledge_dir)
    except KnowledgeValidationError as exc:
        print(f"知识库校验失败: {exc}", file=sys.stderr)
        return 1
    print(
        "知识库校验通过: "
        f"schema={bundle.manifest.schema_version} "
        f"content={bundle.manifest.content_version} "
        f"products={len(bundle.products)} "
        f"risk_patterns={len(bundle.risk_patterns)} "
        f"terms={len(bundle.terms)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
