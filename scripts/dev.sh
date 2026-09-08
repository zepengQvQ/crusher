#!/usr/bin/env bash
# 本地一键提示（不使用 Docker）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "1) 启动后端："
echo "   cd $ROOT/backend-python && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000"
echo
echo "2) 另开终端启动 H5："
echo "   cd $ROOT/frontend-h5 && npm run dev"
echo
echo "Swagger: http://localhost:8000/docs"
echo "H5:      http://localhost:5173"
