"""
P0-01 回归入口（金标 + 否定句）。

错误语义见 tests/api 与 tests/p0_08。

  python tests/p0_01/run_p0_01.py
  python tests/p0_01/run_p0_01.py --only golden
  python tests/p0_01/run_p0_01.py --only negation
"""
from __future__ import annotations

import argparse
import unittest
from pathlib import Path


def main():
    import sys

    parser = argparse.ArgumentParser(description="Run P0-01 frozen regression suite")
    parser.add_argument(
        "--only",
        choices=["all", "golden", "negation"],
        default="all",
        help="选择子集",
    )
    args = parser.parse_args()

    pkg = Path(__file__).resolve().parent
    root = pkg.parents[1]
    if str(root / "backend-python") not in sys.path:
        sys.path.insert(0, str(root / "backend-python"))
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    mapping = {
        "golden": ["test_golden_not_disclosed"],
        "negation": ["test_negation_regression"],
        "all": [
            "test_golden_not_disclosed",
            "test_negation_regression",
        ],
    }
    for mod in mapping[args.only]:
        suite.addTests(loader.loadTestsFromName(f"tests.p0_01.{mod}"))

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
