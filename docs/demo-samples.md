# 演示样例（脱敏）

H5 输入页已内置按钮；完整原文也可直接从下列文件复制。

| # | 场景 | 来源 |
|---|---|---|
| 1 | 结构性存款（正常/缺失披露） | `data/examples.json` 第 1 条；或 H5「结构性存款」 |
| 2 | 消费贷（风险） | `data/examples.json` 第 5 条；或 H5「消费贷」 |
| 3 | 安全文本（零风险） | H5「安全文本（零风险）」 |
| 4 | 否定句（不收违约金） | `tests/fixtures/golden/loan_negation.json` |
| 5 | 失败演示 | H5「模拟模型超时」或 `tests/fixtures/demo/mock_smoke_pack.json` |

固定 mock 冒烟包：`tests/fixtures/demo/mock_smoke_pack.json`  
默认 `.env` 中 `MOCK_MODE=true`，**不需要真实 API Key**，断网也可走通 H5 主流程。
