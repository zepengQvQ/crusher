# 请求链路（P0-02 骨架）

```text
H5 InputPage
  -> POST /api/v1/analyses
  -> AnalyzeTextUseCase.submit + BackgroundTasks.run_mock
  -> InMemoryTaskStore
  -> GET /api/v1/analyses/{task_id}
  -> StatusPage / ReportPage
```

真实规则与 LLM 将在 P0-05/P0-06 接入；当前 `run_mock` 只返回固定报告。
