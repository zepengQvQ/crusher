# 请求链路（当前 Demo）

```text
H5 InputPage
  -> POST /api/v1/analyses
  -> AnalyzeTextUseCase.submit
  -> BackgroundTasks: AnalyzeTextUseCase.run
       preprocess → classify → extract
       → rule_review → evidence_validate → explain
  -> InMemoryTaskStore
  -> GET /api/v1/analyses/{task_id}
  -> StatusPage（步骤卡） / ReportPage（结论+证据）
```

- 默认 `MOCK_MODE=true`：不调用真实大模型，规则与抽取仍真实执行。
- `demo_error=model_timeout|invalid_json|rate_limited`：强制失败，用于演示错误页。
- 主链路不走 MCP，不生成 Mermaid。
