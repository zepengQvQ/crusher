# llm/

和大模型打交道。

| 文件 | 白话 |
|------|------|
| `mock_gateway.py` | 假调用（`MOCK_MODE=true`） |
| `openai_compatible_gateway.py` | 真调用 OpenAI 兼容接口 |

异常类型在 `app/domain/llm_errors.py`。组合根按 `MOCK_MODE` 二选一；真模式缺配置直接报错。
