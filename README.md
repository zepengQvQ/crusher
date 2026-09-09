# 金融话术粉碎机（Demo）

粘贴一段金融条款 → 得到通俗解释、关键参数、带原文证据的风险提示。

> 手机网页（Vue）+ 后端服务（Python）· **不用 Docker** · 默认用「假大模型」演示（可不填 API Key）

## 上手（约 20 分钟）

**需要事先装好：** Python 3.10+（推荐 3.11）、Node 18+

```bash
bash scripts/dev.sh          # 准备配置、虚拟环境、依赖，并打印启动命令

# 终端 1：开后端
source backend-python/.venv/bin/activate
uvicorn app.main:app --reload --app-dir backend-python --port 8000

# 终端 2：开网页
cd frontend-h5 && npm run dev
```

- 网页：http://localhost:5173  
- 后端自带的接口说明书：http://localhost:8000/docs  
- 演示：点「结构性存款 / 消费贷」→ 看报告；再点「模拟模型超时」→ 应进错误页  
- 一键测一遍：`make test`

## 目录（每层都有 `project.md` 白话说明）

```text
frontend-h5/      手机网页
backend-python/   后端服务
knowledge/        规则用的金融知识（JSON）
tests/            自动测试（标准答案、防回退）
docs/             说明文档（从 docs/project.md 进）
contracts/        接口说明书快照（机器导出的）
scripts/          启动、测试用脚本
data/             演示用条款原文（不是主知识库）
legacy/           旧版网页，只对照，别加新功能
```

## 常用命令

```bash
make setup            # 同 scripts/dev.sh
make demo             # 打印演示步骤
make test             # 跑全套 Demo 测试 + 打包检查网页
make export-openapi   # 改完接口后：更新说明书 + 前端类型
```

## 环境变量（根目录 `.env`）

| 变量 | 白话 |
|------|------|
| `MOCK_MODE` | `true`：假大模型（断网可演示）；`false`：真调 DeepSeek（需有效 Key） |
| `LLM_API_KEY` | 只有真调大模型才要填；**不要写进网页** |
| `CORS_ORIGINS` | 允许哪个网页地址来调接口（默认本机 5173） |

模板：`.env.example`

## 常见错误

| 现象 | 处理 |
|------|------|
| 导入不到 `app` | `pip install -e backend-python/.` |
| 网页调不通接口 | 确认终端 1 后端已启动（8000 端口） |
| 任务找不到 | 重启过后端，内存里的旧任务就没了，重新点分析 |
| 想改成真大模型 | `.env` 设 `MOCK_MODE=false` 并填 Key |

## 更多文档

从这里进：**[`docs/project.md`](docs/project.md)**

## 免责声明

仅供学习参考，不构成投资建议；本 Demo 不做用户适当性评估。
