"""本地 JSON 知识库适配器。

构造时经 Pydantic Schema 全量校验；坏契约 / 坏正则直接抛错。
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from app.domain.models.knowledge import (
    KnowledgeManifest,
    ProductKnowledge,
    RiskPatternKnowledge,
    TermKnowledge,
)
from app.infrastructure.knowledge.schemas import load_knowledge_bundle

_DEFAULT_KNOWLEDGE = Path(__file__).resolve().parents[4] / "knowledge"


class LocalFileKnowledgeRepository:
    """从仓库根目录 knowledge/ 加载强类型产品、风险模式与术语。"""

    def __init__(self, knowledge_dir: Path | None = None) -> None:
        self._dir = Path(knowledge_dir) if knowledge_dir else _DEFAULT_KNOWLEDGE
        bundle, compiled = load_knowledge_bundle(self._dir)
        self._manifest = bundle.manifest
        self._products = bundle.products
        self._risk_patterns = bundle.risk_patterns
        self._terms = bundle.terms
        self._compiled = compiled

    def ping(self) -> bool:
        return self._dir.is_dir() and bool(self._products or self._risk_patterns)

    def get_manifest(self) -> KnowledgeManifest:
        return self._manifest

    def list_products(self) -> list[ProductKnowledge]:
        return list(self._products)

    def list_risk_patterns(self) -> list[RiskPatternKnowledge]:
        return list(self._risk_patterns)

    def list_terms(self) -> list[TermKnowledge]:
        return list(self._terms)

    def get_compiled_regex(self, pattern: str) -> re.Pattern[str]:
        if pattern not in self._compiled:
            try:
                self._compiled[pattern] = re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"非法正则无法编译: {pattern!r} ({exc})") from exc
        return self._compiled[pattern]


@lru_cache
def get_default_knowledge_repository() -> LocalFileKnowledgeRepository:
    return LocalFileKnowledgeRepository()
