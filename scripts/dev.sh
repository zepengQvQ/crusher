#!/usr/bin/env bash
# 本地 Demo 启动提示（不用 Docker）。
# 用法：bash scripts/dev.sh
# 可重复执行：始终按 lock / pyproject 同步依赖，不要求手工删目录。
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
  echo "创建后端虚拟环境…"
  python3 -m venv backend-python/.venv
fi
if [[ ! -x backend-python/.venv/bin/python ]]; then
  echo "backend-python/.venv 存在但不可用，请删除后执行：make setup"
  exit 1
fi
# shellcheck disable=SC1091
source backend-python/.venv/bin/activate
echo "同步后端依赖…"
pip install -U pip
pip install -e "backend-python/.[dev]"
if ! pip install -r backend-python/requirements.lock; then
  echo "警告：requirements.lock 安装未完全成功，已用 editable 开发依赖；请检查网络后重试。"
fi

echo "同步前端依赖（npm ci）…"
(cd frontend-h5 && npm ci)

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
