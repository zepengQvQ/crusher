# 金融话术粉碎机 — 本地 MCP 使用说明（P2-10）

MCP 是可选的本地 AI 入口，**不替代** H5 / FastAPI。关闭或不安装 MCP 时，原有功能与 `make test` 不受影响。

## 架构

```text
H5 → FastAPI HTTP ─┐
                   ├→ Application Use Case → Domain/Rules/Knowledge
AI 客户端 → MCP ───┘
```

- FastAPI **不**通过 MCP 调自己。
- Tool / Resource 只调用 `composition_root` 里的现有能力。
- 仅本地 `stdio`；无远程 MCP、无鉴权平台。

## 安装（可选）

```bash
make setup-mcp
# 等价：backend-python/.venv/bin/pip install -r backend-python/requirements-mcp.lock
```

## 启动

```bash
make run-mcp
# 或：
# cd backend-python && MOCK_MODE=true .venv/bin/python -m app.interfaces.mcp.server
```

日志在 **stderr**；**stdout** 仅给 MCP 协议，请勿在业务代码里 `print`。

## Cursor / MCP Host 配置示例

```json
{
  "mcpServers": {
    "crusher-finance": {
      "command": "/绝对路径/crusher/backend-python/.venv/bin/python",
      "args": ["-m", "app.interfaces.mcp.server"],
      "cwd": "/绝对路径/crusher/backend-python",
      "env": {
        "MOCK_MODE": "true",
        "PYTHONPATH": "/绝对路径/crusher/backend-python"
      }
    }
  }
}
```

## MCP Inspector 冒烟

```bash
make setup-mcp
cd backend-python
.venv/bin/pip install "mcp[cli]>=1.9,<2"   # 若需 inspector CLI
npx @modelcontextprotocol/inspector \
  .venv/bin/python -m app.interfaces.mcp.server
```

检查项：

1. Tools 列表恰好为白名单 5 个：`resolve_financial_intent`、`analyze_financial_text`、`compare_financial_products`、`calculate_financial_scenario`、`verify_financial_draft`
2. Resources 可读 `finance://manifest`
3. 调用未知工具名应失败（白名单拦截）

## 测试

```bash
make test-p2-10          # 要求已 make setup-mcp；SDK 协议测试不得静默 skip
make test-p2-rc-07       # RC-07：MCP SDK + 知识来源 + Harness 拆分
make test-p2-rc          # RC-01～07 收口聚合
make test                # 核心全量：未装 mcp 时 SDK 用例可 skip，其余仍通过
```

## 安全边界

- 无任意文件读写、无任意 URL、无 shell。
- Resource URI 仅 `finance://…`，ID 限制安全字符。
- 输出脱敏：去掉 `api_key` / `base_url` 等字段。
