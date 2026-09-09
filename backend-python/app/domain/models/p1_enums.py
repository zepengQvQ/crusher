"""P1 统一枚举：来源类型、对照状态等。"""
from enum import Enum


class SourceType(str, Enum):
    sales_pitch = "sales_pitch"
    official_document = "official_document"
    user_input = "user_input"


class ClaimStatus(str, Enum):
    """销售主张相对正式材料的对照结果。"""

    confirmed = "confirmed"  # 一致
    not_found = "not_found"  # 正式材料未找到
    conflict = "conflict"  # 存在冲突
    conditional = "conditional"  # 正式材料有附加条件
    uncertain = "uncertain"  # 无法判断


class ClaimSubject(str, Enum):
    """可对照的主张主题。"""

    expected_return = "expected_return"
    fee = "fee"
    early_exit = "early_exit"
    principal_protection = "principal_protection"
    term = "term"


class FieldStatus(str, Enum):
    """抽取字段状态（计算器预填等）。"""

    confirmed = "confirmed"
    missing = "missing"
    conflicting = "conflicting"
    uncertain = "uncertain"


class CalculationKind(str, Enum):
    simple_return = "simple_return"
    fee = "fee"
    net_exit = "net_exit"


class DayCountBasis(str, Enum):
    days_360 = "360"
    days_365 = "365"


class DiffStatus(str, Enum):
    """两款产品同一维度的对比状态。"""

    same = "same"
    different = "different"
    missing_a = "missing_a"
    missing_b = "missing_b"
    both_missing = "both_missing"
    incomparable = "incomparable"


class ProductFactDimension(str, Enum):
    product_type = "product_type"
    term = "term"
    amount = "amount"
    return_or_rate = "return_or_rate"
    early_exit = "early_exit"
    fees = "fees"
    principal_protection = "principal_protection"
    main_risks = "main_risks"
    undisclosed = "undisclosed"
