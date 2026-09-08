#!/usr/bin/env bash
# 本地 Demo 启动提示（不用 Docker）。
# 用法：bash scripts/dev.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

need() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "缺少命令：$1"
    exit 1
  fi
}

need python3
need npm

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已复制 .env.example → .env（默认 MOCK_MODE=true，可不填真实 Key）"
fi

if [[ ! -d backend-python/.venv ]]; then
  echo "首次：创建后端虚拟环境并安装依赖…"
  python3 -m venv backend-python/.venv
  # shellcheck disable=SC1091
  source backend-python/.venv/bin/activate
  pip install -U pip
  pip install -e "backend-python/.[dev]"
  pip install -r backend-python/requirements.lock || true
else
  # shellcheck disable=SC1091
  source backend-python/.venv/bin/activate
fi

if [[ ! -d frontend-h5/node_modules ]]; then
  echo "首次：安装前端依赖…"
  (cd frontend-h5 && npm install)
fi

echo
echo "======== 请开两个终端 ========"
echo
echo "【终端 1｜API】"
echo "  cd $ROOT"
echo "  source backend-python/.venv/bin/activate"
echo "  uvicorn app.main:app --reload --app-dir backend-python --port 8000"
echo "  文档：http://localhost:8000/docs"
echo
echo "【终端 2｜H5】"
echo "  cd $ROOT/frontend-h5"
echo "  npm run dev"
echo "  页面：http://localhost:5173"
echo
echo "演示：H5 点示例 → 开始分析；超时演示按钮应进错误页（不是「没风险」）。"
echo "测试：make test"
echo "Mock：.env 中 MOCK_MODE=true（默认），断网也能演示主流程。"
echo
