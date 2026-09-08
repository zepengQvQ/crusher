# Demo 范围冻结（P0-01，后续编号已按此实现）

> 本文是 Demo 的范围锁。**不得临时增加产品类型或页面**；若要扩范围，先改本文并评审。

| 项 | 约定 |
|---|---|
| 文档版本 | P0-01（范围冻结）；实现已完成至 P0-09 |
| 审查基线 | 整改实施清单所述仓库与基线 |
| 服务端 | Python + FastAPI（`backend-python/`） |
| 前端 | Vue3 + Vant H5（`frontend-h5/`） |
| 运行方式 | **不使用 Docker**；本机启动 API + H5（见根 README） |

---

## 1. 支持什么

### 1.1 首批产品类型（仅 2 类）

| 产品 ID | 中文名 | 演示样例来源 | 选择理由 |
|---|---|---|---|
| `structured_deposit` | 结构性存款 | `data/examples.json` 汇率挂钩样例；`tests/case_structured_deposit.json` | 现有用例与参数字段最完整，演示路径清晰 |
| `loan` | 借贷（消费贷） | `data/examples.json` 借贷合同样例 | 条款要素明确（利率/罚息/违约金），适合展示风险发现与否定句回归 |

其它知识库条目（雪球 / 保险 / 基金）**仅用于规则回归与误报防护**，不作为首版 Demo「已支持产品」对外宣称。

### 1.2 用户主流程（冻结）

1. 粘贴一段销售话术或产品说明文本（首版不做 PDF/OCR）。
2. 可选：手动指定产品类型；默认自动识别（可返回多候选，置信度不足则为 `unknown`）。
3. 提交分析 → 获得 `task_id`。
4. 轮询任务状态 → 查看结构化报告，或看到明确失败。

### 1.3 报告必须包含的块

- 产品候选（可多选 + 置信度 / 证据）
- 通俗解释
- 关键参数（原文未写的字段必须是 `not_disclosed`，禁止用行业常识填空）
- 风险发现（Finding）：每条必须能落到原文证据
- 证据列表
- 缺失信息 / 待确认问题
- 阶段状态（成功 / 部分成功 / 失败），**失败不得渲染成「未发现风险」**

### 1.4 接口形态（契约冻结，示例见 `docs/api/`）

| 方法 | 路径 | 作用 |
|---|---|---|
| `POST` | `/api/v1/analyses` | 提交文本分析，立即返回 `task_id` |
| `GET` | `/api/v1/analyses/{task_id}` | 查询任务与阶段结果 / 最终报告 |

字段名与枚举以 `docs/api/*.example.json` 为准；后续 Pydantic / OpenAPI / H5 类型必须对齐，不允许各写一套。

---

## 2. 不支持什么（首版明确不做）

- 不宣称支持雪球、保险、基金的完整演示路径（仅保留回归样例防误报）。
- 不做账户、支付、运营后台、多租户。
- 不做 Redis/Celery/消息队列；任务存储允许单进程内存。
- 不做模型微调、多 Agent、数字人/视频。
- 不做 PDF/图片 OCR（P1）。
- H5 不展示、不接收 API Key / `base_url`。
- 不让模型生成可执行 Mermaid/HTML 直接进页面（后续改为受控步骤卡）。
- 不把「产品风险评级」和「单条发现严重度」混用同一个 `risk_level` 展示名：
  - 产品级：`product_risk_grade`
  - 发现级：`finding_severity`

---

## 3. 怎么演示

### 3.1 推荐演示脚本（约 5 分钟）

1. **正向样例（结构性存款）**  
   粘贴汇率挂钩结构性存款条款 → 展示通俗解释、区间收益参数、区间突破风险与原文高亮。
2. **正向样例（消费贷）**  
   粘贴含罚息/提前还款违约金的贷款条款 → 展示费用与违约相关发现及证据。
3. **失败态（必演）**  
   使用 mock：模型超时或非法 JSON → 页面必须显示「模型调用失败 / 返回格式错误」，**禁止**绿色「未发现风险」。
4. **否定句防误报（可选，验收用）**  
   跑 `tests/fixtures/regression/` 四组样例；P0-05 修复规则后应全部通过。

### 3.2 字段语义：原文未披露

| 旧写法（禁止当金标） | 冻结后写法 |
|---|---|
| `原文未说明` / `未知` / 空字符串当「没有」 | `not_disclosed` |
| 「通常保本，但需以合同为准」等行业常识填入当前材料字段 | 当前材料字段保持 `not_disclosed`；常识如需展示必须标记为 `general_reference`，不得自动写入 `document_fact` |

金标与样例：`tests/fixtures/golden/`、`tests/expected_output_sample.json`。

---

## 4. 回归样本索引（输入与期望只改 fixture，不改断言语义）

| Fixture | 正确结果（冻结） |
|---|---|
| `tests/fixtures/regression/negation_fund_principal_fee.json` | 不得命中「本金不保证」「高额管理费」 |
| `tests/fixtures/regression/negation_loan_prepayment.json` | 不得报告「存在提前还款违约金」 |
| `tests/fixtures/regression/negation_insurance_waiting.json` | 不得报告「等待期内不赔付」 |
| `tests/fixtures/regression/negation_snowball_knock.json` | 不得仅凭「敲入/敲出」识别为雪球产品 |
| `tests/fixtures/regression/error_model_timeout.json` | 任务/阶段为失败，findings 不得被解释为「无风险」 |
| `tests/fixtures/regression/error_illegal_json.json` | 同上，错误码为返回格式错误 |

黑盒测试：`tests/p0_01/`。  
**说明：P0-05 起否定句与数值规则由 `RuleEngine` 复核；四组 `negation_*.json` 应全部通过。**

---

## 5. 同一输入的正确输出约定

对任意 Demo 输入，团队按以下优先级理解「正确」：

1. **文档事实**：只采信输入原文写明的内容。  
2. **未披露**：原文没写 → 结构化字段为 `not_disclosed`，可进入「待确认问题」。  
3. **程序规则**：否定词、数值条件以规则引擎为准；模型不得推翻「不收违约金」类否定结论。  
4. **通俗解释**：措辞可变，但不得引入原文没有的保证（如擅自写保本）。  
5. **失败**：超时 / 非法 JSON / 限流 → 显式失败状态，禁止空 findings 冒充安全。

对首批两个正向样例的字段期望，以 `tests/fixtures/golden/` 为准。
