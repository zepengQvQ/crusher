# knowledge/

规则引擎会读的金融知识（JSON 文件）。启动时经 Pydantic Schema 校验；也可 `make validate-knowledge` 离线校验。

| 文件 | 白话 |
|------|------|
| `manifest.json` | schema/内容版本与最近校验日期 |
| `products.json` | 有哪些产品、别名；行业提示只能当「参考」，不能当成当前合同写了 |
| `risk_patterns.json` | 怎么认风险：关键词、正则、否定词附近不误报、数字条件 |
| `terms.json` | 术语解释（每条有稳定 `id` 与来源元数据） |

来源约定（P2-RC-07）：

- `verification_status`：`VERIFIED` / `UNVERIFIED`。缺可核查外部来源的监管/金额/风险/定义条目必须为 `UNVERIFIED`。
- `source_name` / `source_url` / `source_note` / `verified_at` **不得**仅回指本目录 JSON 自身来证明正确。
- `verified_at` 不得晚于今天，且不得晚于 `manifest.last_verified_at`。
- 未核验知识可进 `general_references`，但不得伪装成已确认结论。

路径相对仓库根目录；后端启动后默认读本目录。
