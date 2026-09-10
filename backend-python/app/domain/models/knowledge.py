"""本地知识库强类型条目（P2-04）。

文档事实与通用知识分通道：通用知识只能进入 general_references，
不能写入 document_fact。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import Field, field_validator, model_validator

from app.domain.models.report import StrictModel


class MatchMode(str, Enum):
    regex_or_keywords = "regex_or_keywords"
    regex_only = "regex_only"
    all_keywords = "all_keywords"


class KnowledgeRiskLevel(str, Enum):
    high = "高"
    medium = "中"
    low = "低"


class NumericOperator(str, Enum):
    gt = ">"
    lt = "<"
    ge = ">="
    le = "<="
    eq = "=="


class NumericRule(StrictModel):
    extract_regex: str = Field(..., min_length=1)
    operator: NumericOperator
    threshold: Decimal
    unit: str | None = None

    @field_validator("threshold", mode="before")
    @classmethod
    def _as_decimal(cls, value: object) -> Decimal:
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"numeric_rule.threshold 非法: {value!r}") from exc


class ProductKnowledge(StrictModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    aliases: list[str] = Field(default_factory=list)
    strong_aliases: list[str] = Field(default_factory=list)
    weak_aliases: list[str] = Field(default_factory=list)
    negation_cues: list[str] = Field(default_factory=list)
    context_window: int = Field(default=16, ge=1, le=128)
    category: str = Field(..., min_length=1)
    definition: str = Field(..., min_length=1)
    typical_terms: list[str] = Field(default_factory=list)
    risk_level_hint: str = ""
    principal_protection_hint: str = ""
    common_risks: list[str] = Field(default_factory=list)
    regulatory_notes: str = ""
    source_name: str = "本地产品知识"
    source_url: str | None = None
    source_note: str = "knowledge/products.json"
    verified_at: date


class RiskPatternKnowledge(StrictModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    keywords: list[str] = Field(default_factory=list)
    regex: str = ""
    match_mode: MatchMode = MatchMode.regex_or_keywords
    context_window: int = Field(default=16, ge=1, le=128)
    applicable_product_types: list[str] = Field(..., min_length=1)
    risk_level: KnowledgeRiskLevel
    explanation: str = Field(..., min_length=1)
    negation_cues: list[str] = Field(default_factory=list)
    max_keyword_span: int = Field(default=48, ge=1, le=500)
    numeric_rule: NumericRule | None = None
    source_name: str = "本地风险模式"
    source_url: str | None = None
    source_note: str = "knowledge/risk_patterns.json"
    verified_at: date

    @model_validator(mode="after")
    def _need_matcher(self) -> RiskPatternKnowledge:
        if self.match_mode == MatchMode.regex_only and not self.regex:
            raise ValueError(f"风险模式 {self.id} 的 match_mode=regex_only 但缺少 regex")
        if self.match_mode == MatchMode.all_keywords and not self.keywords:
            raise ValueError(f"风险模式 {self.id} 的 match_mode=all_keywords 但缺少 keywords")
        if (
            self.match_mode == MatchMode.regex_or_keywords
            and not self.regex
            and not self.keywords
        ):
            raise ValueError(f"风险模式 {self.id} 缺少 regex 与 keywords")
        return self


class TermKnowledge(StrictModel):
    id: str = Field(..., min_length=1)
    term: str = Field(..., min_length=1)
    aliases: list[str] = Field(default_factory=list)
    category: str = Field(..., min_length=1)
    definition: str = Field(..., min_length=1)
    plain_explanation: str = Field(..., min_length=1)
    risk_hint: str = ""
    source_name: str = "本地术语表"
    source_url: str | None = None
    source_note: str = "knowledge/terms.json"
    verified_at: date


class KnowledgeManifest(StrictModel):
    schema_version: str = Field(..., min_length=1)
    content_version: str = Field(..., min_length=1)
    last_verified_at: date


class KnowledgeBundle(StrictModel):
    """一次加载并校验后的完整知识包。"""

    manifest: KnowledgeManifest
    products: list[ProductKnowledge]
    risk_patterns: list[RiskPatternKnowledge]
    terms: list[TermKnowledge]
