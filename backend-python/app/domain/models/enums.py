"""业务枚举：禁止在代码里散落魔法字符串。"""
from enum import Enum

from app.shared.enums import ErrorCode, StageStatus, TaskStatus

__all__ = [
    "ErrorCode",
    "TaskStatus",
    "StageStatus",
    "FactStatus",
    "FindingSeverity",
    "ProductTypeId",
    "ProductHint",
    "AnalysisScope",
    "ParameterKey",
    "DemoErrorKind",
    "EvidenceSource",
]


class FactStatus(str, Enum):
    """字段从哪里来。"""

    document_fact = "document_fact"  # 原文写了
    calculated_fact = "calculated_fact"  # 程序算出来的
    general_reference = "general_reference"  # 行业常识，不能当成本材料事实
    not_disclosed = "not_disclosed"  # 原文没写
    user_asserted = "user_asserted"  # 用户纠错声明，不能伪装成 document_fact
    unknown = "unknown"


class FindingSeverity(str, Enum):
    """单条风险发现的严重度（不要和产品评级混用）。"""

    high = "high"
    mid = "mid"
    low = "low"


class ProductTypeId(str, Enum):
    structured_deposit = "structured_deposit"
    loan = "loan"
    snowball = "snowball"
    insurance = "insurance"
    fund = "fund"
    unknown = "unknown"

    @property
    def label(self) -> str:
        return {
            ProductTypeId.structured_deposit: "结构性存款",
            ProductTypeId.loan: "贷款",
            ProductTypeId.snowball: "雪球结构",
            ProductTypeId.insurance: "保险",
            ProductTypeId.fund: "基金",
            ProductTypeId.unknown: "未识别",
        }.get(self, self.value)


class ProductHint(str, Enum):
    """接口允许的手动产品提示（首版仅自动 / 结构性存款 / 贷款）。"""

    auto = "auto"
    structured_deposit = "structured_deposit"
    loan = "loan"


class AnalysisScope(str, Enum):
    """一次分析的范围状态。"""

    supported = "supported"
    out_of_scope = "out_of_scope"
    needs_confirmation = "needs_confirmation"


class ParameterKey(str, Enum):
    term = "term"
    expected_return = "expected_return"
    early_redemption = "early_redemption"
    fee_structure = "fee_structure"
    principal_protection = "principal_protection"
    product_risk_grade = "product_risk_grade"
    amount = "amount"
    # 消费贷专用
    annual_interest_rate = "annual_interest_rate"
    repayment_method = "repayment_method"
    penalty_interest = "penalty_interest"
    prepayment_fee = "prepayment_fee"


class DemoErrorKind(str, Enum):
    model_timeout = "model_timeout"
    invalid_json = "invalid_json"
    rate_limited = "rate_limited"


class EvidenceSource(str, Enum):
    input_text = "input_text"
    knowledge = "knowledge"
