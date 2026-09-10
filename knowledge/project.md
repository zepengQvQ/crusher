# knowledge/

规则引擎会读的金融知识（JSON 文件）。启动时经 Pydantic Schema 校验；也可 `make validate-knowledge` 离线校验。

| 文件 | 白话 |
|------|------|
| `manifest.json` | schema/内容版本与最近校验日期 |
| `products.json` | 有哪些产品、别名；行业提示只能当「参考」，不能当成当前合同写了 |
| `risk_patterns.json` | 怎么认风险：关键词、正则、否定词附近不误报、数字条件 |
| `terms.json` | 术语解释（每条有稳定 `id` 与来源元数据） |

路径相对仓库根目录；后端启动后默认读本目录。
