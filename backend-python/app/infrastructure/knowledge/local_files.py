"""本地 JSON 知识库适配器。

启动/构造时编译全部正则；坏正则直接抛错，禁止运行时静默跳过。
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

_DEFAULT_KNOWLEDGE = (
    Path(__file__).resolve().parents[4] / "knowledge"
)


class LocalFileKnowledgeRepository:
    """从仓库根目录 knowledge/ 加载产品与风险模式。"""

    def __init__(self, knowledge_dir: Path | None = None) -> None:
        self._dir = Path(knowledge_dir) if knowledge_dir else _DEFAULT_KNOWLEDGE
        self._products = self._load_json("products.json")
        self._risk_patterns = self._load_json("risk_patterns.json")
        self._terms = self._load_json("terms.json")
        self._compiled: dict[str, re.Pattern[str]] = {}
        self._compile_all_regexes()

    def ping(self) -> bool:
        return self._dir.is_dir() and bool(self._products or self._risk_patterns)

    def list_products(self) -> list[dict]:
        return list(self._products)

    def list_risk_patterns(self) -> list[dict]:
        return list(self._risk_patterns)

    def list_terms(self) -> list[dict]:
        return list(self._terms)

    def get_compiled_regex(self, pattern: str) -> re.Pattern[str]:
        if pattern not in self._compiled:
            # 动态 numeric_rule 等：同样不允许坏正则
            try:
                self._compiled[pattern] = re.compile(pattern)
            except re.error as exc:
                raise ValueError(f"非法正则无法编译: {pattern!r} ({exc})") from exc
        return self._compiled[pattern]

    def _load_json(self, filename: str) -> list:
        path = self._dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"知识库文件不存在: {path}")
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"知识库 {filename} 必须是 JSON 数组")
        return data

    def _compile_all_regexes(self) -> None:
        for pattern in self._risk_patterns:
            pid = pattern.get("id", "?")
            regex = pattern.get("regex") or ""
            if regex:
                try:
                    self._compiled[regex] = re.compile(regex)
                except re.error as exc:
                    raise ValueError(
                        f"风险模式 {pid} 的 regex 非法，拒绝启动: {regex!r} ({exc})"
                    ) from exc
            numeric = pattern.get("numeric_rule") or {}
            extract = numeric.get("extract_regex") or ""
            if extract:
                try:
                    self._compiled[extract] = re.compile(extract)
                except re.error as exc:
                    raise ValueError(
                        f"风险模式 {pid} 的 numeric_rule.extract_regex 非法: "
                        f"{extract!r} ({exc})"
                    ) from exc


@lru_cache
def get_default_knowledge_repository() -> LocalFileKnowledgeRepository:
    return LocalFileKnowledgeRepository()
