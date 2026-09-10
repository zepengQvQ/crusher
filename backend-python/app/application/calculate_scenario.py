"""P1-04：用户确认参数后的确定性计算用例。"""
from __future__ import annotations

from app.domain.calculators.fee_calculator import calculate_fee
from app.domain.calculators.net_exit import calculate_net_exit
from app.domain.calculators.simple_return import calculate_simple_return
from app.domain.models.calculation import CalculateScenarioRequest, CalculationResult
from app.domain.models.p1_enums import CalculationKind
from app.domain.validation.publication_service import PublicationService


class CalculateScenarioUseCase:
    def __init__(self, publication: PublicationService | None = None) -> None:
        self._publication = publication or PublicationService()

    def execute(self, req: CalculateScenarioRequest) -> CalculationResult:
        if req.kind == CalculationKind.simple_return:
            if req.principal is None or req.annual_rate_percent is None or req.days is None:
                raise ValueError("简单收益需要本金、年化比例和天数")
            result = calculate_simple_return(
                principal=req.principal,
                annual_rate_percent=req.annual_rate_percent,
                days=req.days,
                day_count_basis=req.day_count_basis,
            )
        elif req.kind == CalculationKind.fee:
            if req.fee_base is None or req.fee_rate_percent is None:
                raise ValueError("比例费用需要计费基数和费率")
            result = calculate_fee(
                fee_base=req.fee_base,
                fee_rate_percent=req.fee_rate_percent,
            )
        elif req.kind == CalculationKind.net_exit:
            if req.principal is None or req.return_amount is None or req.fee_amount is None:
                raise ValueError("退出净结果需要本金、收益和费用")
            result = calculate_net_exit(
                principal=req.principal,
                return_amount=req.return_amount,
                fee_amount=req.fee_amount,
            )
        else:
            raise ValueError(f"不支持的计算类型：{req.kind}")
        return self._publication.finalize_calculation(
            result, user_confirmed=req.user_confirmed
        )
