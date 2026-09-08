# 金融话术粉碎机（Demo）

粘贴金融条款 → 通俗解释、关键参数、带原文证据的风险发现。

> 主路径：**Vue3 H5 + Python FastAPI**。**不用 Docker**。默认 **Mock 模式**，可不填 API Key。

## 20 分钟上手（给 Java 同学）

### 1. 环境

- Python **3.10+**（推荐 3.11）
- Node.js **18+**
- 本机终端（macOS / Linux；Windows 可用 Git Bash）

### 2. 一键准备

```bash
cd crusher
bash scripts/dev.sh
```

脚本会：复制 `.env`、创建 `backend-python/.venv`、安装后端与前端依赖，并打印两个终端的启动命令。

### 3. 启动（两个终端）

```bash
# 终端 1
source backend-python/.venv/bin/activate
uvicorn app.main:app --reload --app-dir backend-python --port 8000

# 终端 2
cd frontend-h5 && npm run dev
```

- API 文档：http://localhost:8000/docs  
- 网页：http://localhost:5173  

### 4. 演示流程

1. 打开 H5，点「结构性存款」或「消费贷」示例 → **开始分析**
2. 状态页看步骤卡（含证据校验）→ 进入报告（结论置顶，可展开原文证据）
3. 再点「模拟模型超时」→ 应进**错误页**（不是「没风险」），可「重新分析」

更多样例：[`docs/demo-samples.md`](docs/demo-samples.md)  
HTTP 示例：[`docs/http/analyze.http`](docs/http/analyze.http)

### 5. 跑测试

```bash
make test
```

## 环境变量（根目录 `.env`）

| 变量 | 说明 |
|------|------|
| `MOCK_MODE` | 默认 `true`：不调真实模型，断网可演示 |
| `LLM_API_KEY` | 仅真实调模型时需要；**不要写进网页** |
| `CORS_ORIGINS` | 默认允许本地 5173 |

完整模板：`.env.example`

## 目录（人话）

```text
frontend-h5/       手机网页
backend-python/    FastAPI 服务（pip 包 crusher-backend）
knowledge/         金融知识 JSON
tests/             金标 / 回归 / e2e
docs/              说明、样例、HTTP 请求
contracts/         OpenAPI 快照
legacy/            旧 Streamlit，仅对照
```

Java 同学找代码：[`docs/java-python-map.md`](docs/java-python-map.md)  
请求链路：[`docs/request-flow.md`](docs/request-flow.md)

## 常用命令

```bash
make setup          # 同 bash scripts/dev.sh
make demo           # 打印演示步骤
make test           # Demo 全量测试 + H5 build
make export-openapi # 更新 contracts/ 与前端类型
make test-api       # 仅接口测试
```

后端锁定依赖：`backend-python/requirements.lock`（前端已有 `package-lock.json`）。

## 调试

- VS Code / Cursor：`.vscode/launch.json`（启动 API、跑 P0-08、导出 OpenAPI）
- 断点建议先打在：`routes.py` → `analyze_text.py` → `domain/rules/engine.py`

## 常见错误

| 现象 | 处理 |
|------|------|
| 导入不到 `app` | `pip install -e backend-python/.` 或 `PYTHONPATH=backend-python` |
| H5 调不通 API | 确认 8000 已起；Vite 已代理 `/api`、`/health` |
| 任务突然找不到 | 内存任务，**重启 API 会丢**；重新点分析 |
| 想关 Mock | `.env` 设 `MOCK_MODE=false` 并填真实 `LLM_API_KEY`（后续可接真模型） |

## 整改清单

[`docs/金融话术粉碎机-整改实施清单.md`](docs/金融话术粉碎机-整改实施清单.md)

## 免责声明

仅供学习参考，不构成投资建议；本 Demo 不进行用户适当性评估。
