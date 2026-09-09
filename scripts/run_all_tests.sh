#!/usr/bin/env bash
# Demo 全量测试入口（不含 legacy Streamlit/Mermaid 旧脚本）。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${ROOT}/backend-python/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "找不到项目虚拟环境：$PY"
  echo "请先执行：make setup"
  exit 1
fi
export PYTHONPATH="${ROOT}/backend-python:${ROOT}:${PYTHONPATH:-}"
# 回归默认走 Mock，避免本机 .env 的 MOCK_MODE=false 打到真模型
export MOCK_MODE="${MOCK_MODE:-true}"

echo "==> API"
"$PY" -m unittest discover -s "${ROOT}/tests/api" -v

echo "==> P0-01 golden + negation"
"$PY" -m unittest \
  tests.p0_01.test_golden_not_disclosed \
  tests.p0_01.test_negation_regression -v

echo "==> P0-RC-01"
"$PY" -m unittest discover -s "${ROOT}/tests/p0_rc_01" -v

echo "==> P0-RC-02"
"$PY" -m unittest discover -s "${ROOT}/tests/p0_rc_02" -v

echo "==> P0-RC-03"
"$PY" -m unittest discover -s "${ROOT}/tests/p0_rc_03" -v

echo "==> P0-RC-04"
"$PY" -m unittest discover -s "${ROOT}/tests/p0_rc_04" -v

echo "==> P0-RC-05"
"$PY" -m unittest discover -s "${ROOT}/tests/p0_rc_05" -v

echo "==> P0-RC-06 gate"
"$PY" -m unittest discover -s "${ROOT}/tests/p0_rc_06" -v

echo "==> P0-RC-07"
"$PY" -m unittest discover -s "${ROOT}/tests/p0_rc_07" -v

echo "==> P0-05"
"$PY" -m unittest discover -s "${ROOT}/tests/p0_05" -v

echo "==> P0-06"
"$PY" -m unittest discover -s "${ROOT}/tests/p0_06" -v

echo "==> P0-07"
"$PY" -m unittest discover -s "${ROOT}/tests/p0_07" -v

echo "==> P0-08"
"$PY" -m unittest discover -s "${ROOT}/tests/p0_08" -v

echo "==> P0-09"
"$PY" -m unittest discover -s "${ROOT}/tests/p0_09" -v

echo "==> H5 vitest"
(cd "${ROOT}/frontend-h5" && npm test)

echo "==> H5 build"
(cd "${ROOT}/frontend-h5" && npm run build)

echo "ALL DEMO TESTS PASSED"
