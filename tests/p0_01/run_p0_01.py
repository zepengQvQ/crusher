"""
P0-01 回归入口。

默认运行全部 P0-01 用例。否定句 / 错误语义在规则修复前会失败，这是预期现象。

  python tests/p0_01/run_p0_01.py
  python tests/p0_01/run_p0_01.py --only golden   # 只跑金标审核（应通过）
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
        choices=["all", "golden", "negation", "error"],
        default="all",
        help="选择子集；golden 在 P0-01 完成后应通过",
    )
    args = parser.parse_args()

    pkg = Path(__file__).resolve().parent
    root = pkg.parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    legacy = root / "legacy"
    if str(legacy) not in sys.path:
        sys.path.insert(0, str(legacy))

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    mapping = {
        "golden": ["test_golden_not_disclosed"],
        "negation": ["test_negation_regression"],
        "error": ["test_error_semantics"],
        "all": [
            "test_golden_not_disclosed",
            "test_negation_regression",
            "test_error_semantics",
        ],
    }
    for mod in mapping[args.only]:
        suite.addTests(loader.loadTestsFromName(f"tests.p0_01.{mod}"))

    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
