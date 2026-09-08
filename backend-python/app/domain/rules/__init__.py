"""领域规则包：否定句、产品识别、事实抽取、证据校验。"""

from app.domain.rules.engine import ProductHit, RiskHit, RuleEngine
from app.domain.rules.evidence import validate_and_fix_findings
from app.domain.rules.fact_extractor import ExtractResult, FactExtractor

__all__ = [
    "RuleEngine",
    "ProductHit",
    "RiskHit",
    "FactExtractor",
    "ExtractResult",
    "validate_and_fix_findings",
]