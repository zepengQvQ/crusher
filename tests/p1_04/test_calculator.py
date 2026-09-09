"""P1-04：Decimal 简单计算器验收。"""
from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from fastapi.testclient import TestClient  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from app.application.calculate_scenario import CalculateScenarioUseCase  # noqa: E402
from app.domain.models.calculation import CalculateScenarioRequest  # noqa: E402
from app.domain.models.p1_enums import CalculationKind, DayCountBasis  # noqa: E402
from app.main import create_app  # noqa: E402


class CalculatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.uc = CalculateScenarioUseCase()

    def test_golden_simple_return(self) -> None:
        # 100000 × 3.65% × 90 ÷ 365 = 900.00
        req = CalculateScenarioRequest(
            kind=CalculationKind.simple_return,
            user_confirmed=True,
            principal="100000",
            annual_rate_percent="3.65",
            days="90",
            day_count_basis=DayCountBasis.days_365,
        )
        out = self.uc.execute(req)
        self.assertEqual(out.result, "900.00")
        self.assertIn("÷ 365", out.formula)
        self.assertNotIn("float", out.rounding.lower())

    def test_thousand_separator(self) -> None:
        req = CalculateScenarioRequest(
            kind=CalculationKind.simple_return,
            user_confirmed=True,
            principal="100,000",
            annual_rate_percent="3.65%",
            days="90",
            day_count_basis=DayCountBasis.days_365,
        )
        self.assertEqual(self.uc.execute(req).result, "900.00")

    def test_fee(self) -> None:
        req = CalculateScenarioRequest(
            kind=CalculationKind.fee,
            user_confirmed=True,
            fee_base="100000",
            fee_rate_percent="0.5",
        )
        out = self.uc.execute(req)
        self.assertEqual(out.result, "500.00")

    def test_net_exit(self) -> None:
        req = CalculateScenarioRequest(
            kind=CalculationKind.net_exit,
            user_confirmed=True,
            principal="100000",
            return_amount="900.00",
            fee_amount="500",
        )
        self.assertEqual(self.uc.execute(req).result, "100400.00")

    def test_reject_unconfirmed(self) -> None:
        with self.assertRaises(ValidationError):
            CalculateScenarioRequest(
                kind=CalculationKind.fee,
                user_confirmed=False,
                fee_base="1",
                fee_rate_percent="1",
            )

    def test_reject_missing_fields(self) -> None:
        req = CalculateScenarioRequest(
            kind=CalculationKind.simple_return,
            user_confirmed=True,
            principal="100000",
        )
        with self.assertRaises(ValueError):
            self.uc.execute(req)

    def test_reject_rate_range(self) -> None:
        req = CalculateScenarioRequest(
            kind=CalculationKind.simple_return,
            user_confirmed=True,
            principal="100000",
            annual_rate_percent="3%-5%",
            days="90",
        )
        with self.assertRaises(ValueError) as ctx:
            self.uc.execute(req)
        self.assertIn("区间", str(ctx.exception))

    def test_reject_negative_principal(self) -> None:
        req = CalculateScenarioRequest(
            kind=CalculationKind.simple_return,
            user_confirmed=True,
            principal="-1",
            annual_rate_percent="3.65",
            days="90",
        )
        with self.assertRaises(ValueError):
            self.uc.execute(req)

    def test_reject_zero_days(self) -> None:
        req = CalculateScenarioRequest(
            kind=CalculationKind.simple_return,
            user_confirmed=True,
            principal="100000",
            annual_rate_percent="3.65",
            days="0",
        )
        with self.assertRaises(ValueError):
            self.uc.execute(req)

    def test_reject_empty(self) -> None:
        req = CalculateScenarioRequest(
            kind=CalculationKind.fee,
            user_confirmed=True,
            fee_base="",
            fee_rate_percent="1",
        )
        with self.assertRaises(ValueError):
            self.uc.execute(req)

    def test_reject_bp(self) -> None:
        req = CalculateScenarioRequest(
            kind=CalculationKind.fee,
            user_confirmed=True,
            fee_base="100000",
            fee_rate_percent="50bp",
        )
        with self.assertRaises(ValueError):
            self.uc.execute(req)

    def test_zero_fee_allowed(self) -> None:
        req = CalculateScenarioRequest(
            kind=CalculationKind.fee,
            user_confirmed=True,
            fee_base="100000",
            fee_rate_percent="0",
        )
        self.assertEqual(self.uc.execute(req).result, "0.00")

    def test_no_float_in_pipeline(self) -> None:
        req = CalculateScenarioRequest(
            kind=CalculationKind.simple_return,
            user_confirmed=True,
            principal="100000",
            annual_rate_percent="3.65",
            days="90",
            day_count_basis=DayCountBasis.days_365,
        )
        out = self.uc.execute(req)
        self.assertIsInstance(Decimal(out.result), Decimal)
        for v in out.inputs.values():
            self.assertIsInstance(v, str)

    def test_http_ok(self) -> None:
        client = TestClient(create_app())
        res = client.post(
            "/api/v1/calculations",
            json={
                "kind": "simple_return",
                "user_confirmed": True,
                "principal": "100000",
                "annual_rate_percent": "3.65",
                "days": "90",
                "day_count_basis": "365",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["result"], "900.00")

    def test_http_reject_unconfirmed(self) -> None:
        client = TestClient(create_app())
        res = client.post(
            "/api/v1/calculations",
            json={
                "kind": "fee",
                "user_confirmed": False,
                "fee_base": "1",
                "fee_rate_percent": "1",
            },
        )
        self.assertIn(res.status_code, (400, 422))


if __name__ == "__main__":
    unittest.main()
