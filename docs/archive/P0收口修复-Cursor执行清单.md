# 金融话术粉碎机 P0 收口修复清单（给 Cursor）

> **一句话重点：现有项目结构不用再重构；暂停 P1，依次补齐真实模型、规则正确性、产品专属字段、任务原文绑定、输入契约和可信测试门禁。**

## 1. 使用方式

将本文件加入 Cursor 上下文，并发送：

```text
请先完整阅读《金融话术粉碎机-P0收口修复-Cursor执行清单.md》和仓库根目录 README.md。
以当前 main 最新提交为基线，严格按照文档顺序执行。
现在只处理 P0-RC-01；先增加能够复现问题的失败测试，再修改实现，直到本项验收全部通过。
完成后停止，不自动开始下一项。汇报修改文件、关键设计、测试命令和测试结果。
```

完成一项后，把编号替换成下一项。不要让 Cursor 一次性同时改完全部事项。

## 2. 基线与边界

| 项目 | 约定 |
|---|---|
| 仓库 | `https://github.com/zepengQvQ/crusher.git` |
| 分支 | 只处理 `main` |
| 审查基线 | `main@f748a8e` 或它之后的最新提交 |
| 项目定位 | 本地运行的金融话术粉碎机 Demo |
| 前端 | Vue 3 + Vant H5 |
| 后端 | Python + FastAPI 模块化单体 |
| 模型配置 | 后端一个 OpenAI-compatible API Key |
| 团队 | 以 Java 开发为主，Python 代码必须强类型、分层清楚、注释解释业务 |

### 2.1 本轮明确不做

- 不重新规划或搬迁 `frontend-h5/`、`backend-python/`、`domain/` 等目录。
- 不做 Docker、微服务、Redis、Celery、数据库、账号、权限、部署和监控平台。
- 不做 PDF/OCR、双材料对比、产品 PK、追问、计算器、报告保存分享；这些仍属于 P1。
- 不做多 Agent、MCP 主链路、向量数据库、模型训练或微调。
- 不在 H5 增加 API Key、模型名称或供应商地址输入框。
- 不搭建多供应商路由、流式输出、重试平台、熔断器或复杂 harness。
- 不用假的 `@Service`、`@Repository` 等装饰器模仿 Java。

### 2.2 修改前检查

```bash
git status --short --branch
git log -1 --oneline
make test
```

- 如果工作区存在不属于本任务的修改，保留并避开，不得执行 `git reset --hard`、`git checkout -- .` 等覆盖操作。
- 每一项都遵循：**新增失败测试 → 确认测试确实失败 → 修改实现 → 本项测试通过 → 全量回归通过**。
- 不得为了让测试通过而删除断言、放宽期望或把错误结果改成新的“金标”。

## 3. 当前问题汇总

| 执行顺序 | 问题 | 当前表现 | 完成标志 |
|---:|---|---|---|
| P0-RC-01 | 真模型链路不存在 | `MOCK_MODE=false` 仍注入 Mock，模型返回值被丢弃 | Mock/真实网关正确切换，真实返回用于通俗解释，错误语义可验证 |
| P0-RC-02 | 规则仍有误报、漏报 | 普通日利率误报罚息、跨句拼接风险、否定产品仍被识别 | 反例全部通过，证据落在同一原文语句 |
| P0-RC-03 | 两类产品共用投资字段 | 贷款出现“投资期限、提前赎回、本金保障”等不合适字段 | 结构性存款和贷款分别输出自己的关键字段 |
| P0-RC-04 | 原文没有与任务绑定 | 打开旧任务可能显示最新草稿或空原文 | 原文由 `taskId` 对应任务返回，浏览器不持久保存全文 |
| P0-RC-05 | POST 输入未进入 OpenAPI | Swagger 没有 `requestBody`，前端没有请求 DTO | FastAPI 请求模型成为唯一契约源，生成物完全同步 |
| P0-RC-06 | 测试和 lint 会假绿 | H5 只查源码字符串；`make lint` 出错仍返回 0 | 两条真实组件流程测试，lint 失败时命令失败 |

> 顺序说明：P0-RC-05 虽然重要，但放在业务 DTO 稳定以后统一导出 OpenAPI，避免 P0-RC-03、P0-RC-04 修改字段时反复生成契约。

---

# 4. 详细执行事项

## P0-RC-01：接通真实模型并保留稳定 Mock

### 目的

让 README 中“`MOCK_MODE=false` + 后端 API Key 可以调用真模型”变成真实能力，同时保证断网 Mock 演示不受影响。

### 当前问题

- `backend-python/app/composition_root.py` 无条件创建 `MockLlmGateway`。
- `backend-python/app/config/settings.py` 中的 Key、Base URL、模型、温度等没有真正参与调用。
- `backend-python/app/application/analyze_text.py` 调用 `complete()` 后丢弃返回值，报告仍是固定字符串。
- 当前超时、限流、非法 JSON 只是由请求参数 `demo_error` 人工触发，并没有验证真实 Gateway 的异常转换。
- 模型调用发生在 `explain`，异常却被标记到 `extract` 阶段。

### 实现要求

1. 在 `backend-python/app/infrastructure/llm/` 增加一个通用的 OpenAI-compatible 异步适配器，例如：

   ```text
   openai_compatible_gateway.py
   ```

2. 优先直接使用 `httpx.AsyncClient` 调用标准 Chat Completions：

   ```text
   POST {LLM_BASE_URL 去掉末尾斜杠}/chat/completions
   Authorization: Bearer {LLM_API_KEY}
   ```

   不引入某个供应商专用 SDK；`httpx` 必须进入后端正式依赖，而不是只存在于开发依赖。

3. 组合根必须按配置选择实现：

   - `MOCK_MODE=true` → `MockLlmGateway`
   - `MOCK_MODE=false` → `OpenAiCompatibleLlmGateway`

4. 真实模式缺少 `LLM_API_KEY`、`LLM_BASE_URL` 或 `LLM_MODEL` 时，启动或首次构造依赖时给出明确配置错误，不能悄悄退回 Mock。

5. 调整 `LlmGateway` Protocol，使输入输出边界是明确类型。在 `backend-python/app/domain/models/`（或另一个可被 Domain Port 单向依赖的共享模型位置）定义小型 Pydantic 模型，禁止把它放在 Infrastructure/Application 后再让 Protocol 反向导入：

   ```python
   class LlmExplanation(BaseModel):
       plain_language: str
   ```

   Java 对照：`LlmGateway` 是 interface，`LlmExplanation` 是返回 DTO。

6. Prompt 要求模型只返回包含 `plain_language` 的 JSON。适配器或应用边界使用 Pydantic 校验：

   - 允许去掉最外层的 Markdown JSON 代码围栏。
   - 不做猜字段、补字段、无限 JSON 修复。
   - 缺字段、空内容、供应商响应结构错误均视为非法模型输出。

7. `report.plain_language.text` 必须真正使用模型返回内容。产品候选、关键参数、风险 Finding 和 Evidence 仍以程序规则为准，模型不得覆盖。

8. 错误映射至少覆盖：

   | 情况 | 错误码 | 失败阶段 |
   |---|---|---|
   | `httpx.TimeoutException` | `MODEL_TIMEOUT` | `explain` |
   | HTTP 429 | `RATE_LIMITED` | `explain` |
   | 响应 JSON 非法、缺少 `choices[0].message.content`、内容 DTO 非法 | `INVALID_MODEL_JSON` | `explain` |
   | 其他上游错误 | `INTERNAL_ERROR` 或项目新增的单一模型上游错误码 | `explain` |

9. 不得在日志、异常文本、`/health`、H5 或响应中输出 API Key、Authorization 请求头和完整 Prompt/模型响应。

10. `MockLlmGateway` 也返回同一个强类型 `LlmExplanation`，确保 Mock 与真实模式走同一条后续报告组装路径。

### 必须先增加的测试

使用依赖注入或 `httpx.MockTransport`，测试不得访问公网、不得使用真实 Key。

1. `MOCK_MODE=true` 时选择 `MockLlmGateway`，不发送网络请求，输出稳定。
2. `MOCK_MODE=false` 时选择真实适配器，不得仍是 Mock。
3. 模拟 200 响应，断言 `choices[0].message.content` 中的 `plain_language` 最终进入 `report.plain_language.text`。
4. 当程序已有 Finding，而模型返回“未发现风险”“没有风险”等相反结论时，将该输出视为 `INVALID_MODEL_JSON`（非法模型输出），任务失败且 `report=None`；不得把矛盾文案写进 `plain_language`，也不得删除程序 Finding 来迁就模型。
5. 429 → `RATE_LIMITED`，任务失败且 `report=None`。
6. 超时 → `MODEL_TIMEOUT`，任务失败且 `report=None`。
7. 非 JSON、空 choices、空 content、错误内容 DTO → `INVALID_MODEL_JSON`。
8. 真实模式缺 Key/Base URL/模型时明确失败，不能退回 Mock。

### 验收

- Mock 模式断网仍可完成完整报告。
- 真实模式通过模拟 HTTP 响应能够完成报告，返回文案确实进入报告。
- 真实异常不依赖 `demo_error` 也能映射到正确错误码。
- 模型错误显示为失败，不出现“无风险”报告。
- API Key 仅由后端环境变量读取。

### 禁止顺手扩展

- 不做流式 SSE/WebSocket。
- 不做多模型自动选择、fallback、计费统计和对话历史。
- 不让模型直接生成 Finding、证据位置或最终 HTML。

---

## P0-RC-02：修复规则边界、否定和证据质量

### 目的

先把当前已经复现的业务误报消掉，避免 P1 在错误规则上继续堆功能。

### 当前可复现错误

| 输入 | 当前错误结果 | 正确结果 |
|---|---|---|
| `本贷款日利率为0.03%，按日计息。` | 命中“高额逾期罚息” | 不命中，因为没有罚息语义 |
| `本贷款支持提前还款。逾期行为另收违约金。` | 命中“提前还款违约金” | 不得跨句组合两个关键词 |
| `本产品不是贷款，只是普通客服说明。` | 识别为贷款 | 贷款候选应被否定 |
| `本合同仅介绍活期存款利率，与本产品收益无关。` | 可能命中“区间外收益骤降” | 不命中 |
| `保险等待期为30天。` | 可能命中“等待期内不赔付” | 只说明期限，不等于不赔付 |
| `不收申购费，管理费为1.5%。` | “不收”可能错误抑制管理费风险 | 否定不得跨分句影响管理费 |

另外，H5 当前结构性存款示例包含“突破区间后收益下降”，实际返回 0 个风险，与演示说明不一致。

### 实现要求

1. 正向条件组合以强句界 `。！？；\n` 为边界；同一强句内可以跨逗号组合，但必须设置合理最大距离，因此“逾期，按罚息利率计收”仍是合法正例。
2. 否定词采用更严格边界：从目标关键词向前搜索时，遇到 `，,；;。！？\n` 任一边界立即停止。因此“不收申购费，管理费为1.5%”中的“不收”不得否定“管理费”。
3. `all_keywords` 的关键词必须处于同一强句内并满足最大距离，禁止全文拼接。
4. 默认模式不得因为出现一个泛化词就直接命中高风险：

   - “日利率”不能单独触发高额罚息。
   - “等待期”不能单独触发等待期不赔付。
   - “赎回费”不能单独证明存在惩罚性费率。
   - “活期存款利率”不能单独证明区间外收益骤降。

5. 对首批两个产品写清楚触发条件：

   - `high_penalty_interest`：同一语句中必须存在“罚息”以及倍数、罚息日利率或明显高于正常利率的条件。
   - `prepayment_penalty`：同一语句中必须存在“提前还款”以及违约金/手续费/费用/比例；“不收、免收、无需支付”时不得命中。
   - `low_floor_return`：同一语句中必须表达突破/离开观察区间后，仅获得明显较低收益。

6. 产品识别的否定词补充“不是、并非、不属于、不是……产品”等表达，否定判断不得跨句影响后文真正出现的产品。
7. 修改 `is_negated_near` 时按第 2 条的标点边界处理，不能只靠固定字符窗口跨标点查找。
8. Finding 的 `Evidence.quote` 优先返回能够独立看懂的原文分句，而不是只有“日利率”“违约金”这样的单个词；`start/end` 必须与原文完全对应。
9. 修正 H5 结构性存款示例或规则，使推荐演示确实能展示区间收益下降风险；不要修改成与产品逻辑不符的夸张文案。
10. 当自动识别结果为 `unknown`，或只识别到雪球、基金、保险等非首批支持产品时，不得使用 `product_type=None` 执行全部产品规则。固定输出为：

   - `product_candidates`：无法识别时只含 `unknown`；识别到非首批产品时只保留该已识别候选，并在文案中标明 `out of scope`。
   - `key_parameters=[]`
   - `findings=[]`
   - `missing_disclosures=[]`
   - `pending_questions` 只保留一项：“当前 Demo 仅支持结构性存款和贷款，请重新选择或补充材料。”

   不得套用默认投资字段，也不得对非支持产品给出“已完成风险分析”的错觉。

### 必须增加的测试

- 将上表 6 条全部变成回归测试。
- 保留原有四组否定句测试，不能只针对新增文案打补丁。
- 增加同义正例，确认修复误报后没有把真正风险全部过滤：

  ```text
  逾期部分按罚息日利率0.05%计收，罚息为正常利率的2.5倍。
  提前还款需支付剩余本金3%的违约金。
  若汇率突破观察区间，则仅获得1.20%的低档收益。
  ```

- 断言每个 Finding 的 quote 等于 `text[start:end]`，且 quote 包含完整风险条件。
- 增加 `unknown` 与一个非首批产品用例，精确断言 `key_parameters/findings/missing_disclosures` 均为空，且只有一项范围提示。

### 验收

- 所有反例不误报，所有正例仍命中。
- 规则不跨句组合关键词，否定不跨句误伤。
- 默认结构性存款和消费贷演示均能展示预期结果。
- 同一输入重复执行的结构化风险结论一致。

### 禁止顺手扩展

- 不扩展雪球、基金、保险的完整业务能力；仅保留必要回归防误报。
- 不引入 NLP 服务、分词平台、向量检索或模型裁决规则。

---

## P0-RC-03：按产品拆分关键参数抽取

### 目的

让首批正式支持的“结构性存款”和“消费贷”分别展示符合业务语义的字段，不再把贷款套进投资产品模板。

### 实现要求

1. 在 `FactExtractor` 内使用两套清晰的小型配置或两个私有方法：

   ```text
   extract_structured_deposit(...)
   extract_loan(...)
   ```

   不建设通用规则平台或动态 Schema 引擎。

2. 结构性存款至少包含：

   - 产品期限
   - 预期/到期收益率，可保留多个区间值
   - 提前赎回/支取
   - 费用结构
   - 本金保障
   - 原文明示的产品风险评级（如存在）

3. 消费贷至少包含：

   - 借款期限
   - 年化利率
   - 还款方式
   - 罚息约定
   - 提前还款及违约金/手续费
   - 借款金额（原文存在时）

4. 为贷款增加语义明确的 `ParameterKey`，例如：

   ```text
   annual_interest_rate
   repayment_method
   penalty_interest
   prepayment_fee
   ```

   不再把贷款年利率标成“预期收益”，也不再向贷款用户追问“是否承诺本金保障”。

5. 只对当前产品相关字段输出 `not_disclosed` 和待确认问题；无关字段直接不进入该产品报告。
6. 支持常见中文格式和标点：

   ```text
   产品期限：90天
   期限为 90 天
   年化收益率：4.8%
   年化利率（单利）为7.20%
   借款期限12个月
   等额本息还款
   ```

7. `amount` 继续使用 `Decimal`，不得用 `float` 表示金额。
8. 如果原文明确出现“风险等级：R3”或“产品风险评级 R2”，填入 `product_risk_grade=document_fact`；否则保持 `not_disclosed`。
9. `missing_disclosures` 与 `pending_questions` 不得在 H5 中重复显示同一个问题。可以只保留结构化的 `missing_disclosures`，或在组装报告时去重。

### 必须增加或调整的金标测试

1. 结构性存款：冒号格式、多个收益率、未说明本金保障。
2. 消费贷：年化利率、借款期限、等额本息、罚息、提前还款违约金。
3. 消费贷缺失样例：只对贷款相关字段标记 `not_disclosed`。
4. 贷款报告中断言不存在以下 label：

   ```text
   投资期限
   预期收益
   提前赎回
   本金保障
   ```

5. 有明确 `R1`～`R5` 时正确提取；没有时不得用知识库提示填充。
6. 原有“行业常识不得填入材料事实”测试继续通过。

### 验收

- 两个产品的报告字段和问题列表符合各自业务含义。
- `not_disclosed` 只表示“该产品相关但材料没写”，不再表示“不适用于该产品”。
- H5 仍使用通用参数卡片渲染，不复制两套报告页面。
- 修改枚举后暂时记录需要更新 OpenAPI 的内容，统一在 P0-RC-05 生成。

---

## P0-RC-04：让原文、报告和失败重试绑定同一 taskId

### 目的

避免打开旧任务时展示或复制另一个任务的输入，同时满足刷新后恢复任务和失败重试。

### 推荐的最小实现

1. 在单进程内存模型中增加任务所属的 `source_text`：

   - `AnalysisTask.source_text`
   - `TaskResponse.source_text`

2. `AnalyzeTextUseCase.submit()` 创建任务时保存当前请求原文。原文只存在当前进程内存中，服务重启后随任务一起丢失，符合 Demo 边界。
3. GET 任务接口对成功、处理中和失败任务均返回与该 `task_id` 对应的 `source_text`。
4. H5 报告页只能使用 GET 返回的 `source_text`，不能使用一个全局草稿冒充当前任务原文。
5. 删除完整正文写入 `sessionStorage` 的逻辑：

   - `sessionStorage` 只允许保存 `taskId`、任务状态和产品选择。
   - Pinia 可以在当前 SPA 生命周期内临时保存尚未提交的草稿，刷新后未提交草稿丢失可以接受。

6. 失败页重试时：

   - 路由改为 `/error/:taskId?`（或效果完全等价的 query 方案），失败任务跳转时必须携带 `taskId`。
   - ErrorPage 有 `taskId`：先 GET 该任务，使用响应中的 `source_text`，刷新错误页后仍可恢复。
   - ErrorPage 无 `taskId`：仅限 POST 尚未成功创建任务的网络错误，使用 Pinia 当前内存草稿。
   - 不得在有 `taskId` 时回退到全局草稿，以免把另一个任务的原文用于重试。

7. “清空”按钮必须同时清空输入框和 Pinia 内存草稿。
8. 直接打开 `/report/:taskId` 时：

   - `queued/running` → 返回状态页继续查询。
   - `failed` → 进入错误页。
   - `completed + report` → 展示报告。
   - 404 → 显示“任务可能因服务重启而丢失”，不要显示成普通断网。

9. 报告页展示全部产品候选、置信度和识别证据；不能只显示第一个候选并造成“已经确定产品”的错觉。
10. 缺失信息和待确认问题去重后再展示。

### 状态轮询顺手修复

- 不使用可能重叠的 `setInterval(async poll)`。
- 上一次 GET 完成后再通过 `setTimeout` 安排下一次查询。
- 一次临时网络失败不得永久停止；最多自动重试 3 次，然后提供“重新查询当前任务”。
- “重新查询”不得创建新任务；“重新分析”才创建新任务。
- 页面卸载后设置 active 标记或取消请求，禁止旧请求完成后把用户从别的页面拉回报告页。

### 必须增加的测试

1. 连续创建任务 A、任务 B，分别 GET，两个 `source_text` 必须与各自输入一致。
2. 打开任务 A 报告时，即使当前 Pinia 草稿是 B，也只能显示 A 的原文。
3. sessionStorage 中不存在完整输入正文。
4. 失败任务可从任务响应恢复原文并重新提交。
5. 查询中的任务直接进入 report URL 时会跳回 status，而不是显示“报告不存在”。
6. 第一次 GET 网络失败、第二次成功时仍能进入报告页。
7. 多候选报告展示候选名称、置信度和证据。

### 验收

- 原文、证据位置、复制内容和报告始终属于当前 `taskId`。
- 刷新已创建任务后可以重新 GET 恢复；后端重启导致 404 时提示准确。
- 浏览器持久存储中没有金融原文全文。
- 不增加数据库、历史记录列表、加密存储或账号体系。

---

## P0-RC-05：恢复 FastAPI 请求契约和 OpenAPI 同源

### 目的

让 Swagger、Cursor、前端和后端看到同一份请求定义，避免手写字段漂移。

### 当前问题

`POST /api/v1/analyses` 接收裸 `Request` 并手动执行 `request.json()`，因此 OpenAPI 没有 `requestBody`，生成文件中也没有请求 DTO。

### 实现要求

1. 路由函数直接声明 Pydantic 请求体，例如：

   ```python
   async def create_analysis(
       body: CreateAnalysisRequest,
       background_tasks: BackgroundTasks,
       ...,
   ) -> CreateAnalysisResponse:
   ```

2. 请求 DTO 只能有一份权威定义，禁止 HTTP 层 `AnalyzeBody` 与应用层 `AnalyzeTextRequest` 长期保留两套重复字段。
3. 增加 `ProductHint` 枚举，首版只允许：

   ```text
   auto
   structured_deposit
   loan
   ```

   非法值必须返回 4xx，不能静默退回自动识别。
   自动识别可以在内部保留更广的知识条目用于回归，但接口正常报告只承认结构性存款和贷款；雪球、基金、保险不得因自动识别而伪装成首版已支持产品。

4. `locale` 当前只允许 `zh-CN`；不为一个 Demo 提前建设多语言框架。
5. `text` 必须在去除首尾空白后非空，并受 `MAX_INPUT_CHARS` 限制。
6. 非法 JSON、空白文本、非法枚举和多余字段返回稳定 4xx，不得抛未处理 500，也不要把内部 `str(exc)` 原样返回 H5。
7. `api_key`、`llm_api_key`、`base_url`、`token` 等客户端字段继续被拒绝。使用 `extra="forbid"` 即可；如果必须保留 `FORBIDDEN_CLIENT_CONFIG`，只增加一个小型校验异常映射，不要继续裸读 Request。
8. `demo_error` 只允许在 `MOCK_MODE=true` 时使用；真实模式传入时拒绝，避免测试开关进入真实调用路径。
9. `TaskResponse.source_text`、HTTP 请求/响应 DTO、`ProductHint` 和新增 `ParameterKey` 进入 Pydantic/OpenAPI。`LlmExplanation` 是内部网关 DTO，不得暴露到 OpenAPI。
10. 执行：

   ```bash
   make export-openapi
   ```

   更新：

   - `contracts/openapi.json`
   - `frontend-h5/src/api/generated-types.js`

11. 为 `frontend-h5/src/api/client.js` 的请求和返回值补 JSDoc 类型引用；本轮不把整个前端改写成 TypeScript。

### 必须增加的契约测试

1. 实时 `create_app().openapi()` 中 POST 存在 `requestBody`。
2. OpenAPI components 中存在请求 DTO 和 `ProductHint`。
3. `contracts/openapi.json` 与实时 OpenAPI 结构完全一致。
4. 前端生成类型包含请求 DTO、`TaskResponse.source_text` 和所有新枚举。
5. 合法请求成功。
6. 空白文本、非法 `product_hint`、超长文本、客户端 Key/Base URL、非法 JSON 均返回明确 4xx。

### 验收

- Swagger 页面可以直接看到并填写完整 POST 请求体。
- Cursor/Java 开发从 OpenAPI 就能知道全部字段和枚举。
- 修改后端 Schema 后，生成物不一致会导致测试失败。
- H5 请求字段不再靠人工记忆维护。

---

## P0-RC-06：让 H5 测试、lint 和本地启动结果可信

### 目的

消除“测试数量很多但关键功能没真正执行”和“检查失败仍显示成功”的假绿。

### H5 测试要求

1. 使用 Vitest + Vue Test Utils + jsdom 增加最少两条真实组件流程测试：

   - 成功：输入 → POST → 状态轮询 → 报告，验证原文、风险和产品候选。
   - 失败：模型失败 → 错误页 → 保留正确原文 → 重试，验证失败不会显示成“无风险”。

2. API 使用 `vi.mock` 或轻量 mock，不启动公网、不使用真实模型。
3. 至少再覆盖 P0-RC-04 中的“双任务原文不能串线”和“一次轮询失败后恢复”。可以合并进上面两条流程，不要求堆很多测试文件。
4. 原来的源码 `assertIn("重试")` 类测试只能作为结构检查，不得再命名为端到端或 H5 冒烟测试。
5. `frontend-h5/package.json` 增加稳定命令，例如：

   ```json
   "test": "vitest run"
   ```

6. `scripts/run_all_tests.sh` 必须执行 H5 测试和 H5 build。

### Python/Java 可读性和门禁

1. 修复 `Makefile`：

   - 使用 `backend-python/.venv/bin/ruff` 和正确的 Pyright Python 路径。
   - 删除 `|| true`。
   - 检查失败必须返回非 0。

2. Ruff 只检查 `backend-python/app` 主代码；修复当前问题。FastAPI `Depends` 的 `B008` 冲突优先使用 `Annotated[..., Depends(...)]`；若现有框架写法确实无法规避，只允许对 routes 单文件做最小忽略，不得全局关闭大量规则。
3. 保持当前 Pyright 级别，只修复本轮改动产生或暴露的类型错误；本轮不升级到 `strict`。
4. `scripts/dev.sh` 和测试脚本不得吞掉失败；找不到项目 venv 时明确提示先执行 `make setup` 并返回非 0，不要静默切到未知系统 Python。
5. 本轮新增或修改的公开边界避免未类型化的 `dict`、`list` 和 `Any`；不追溯重构整个知识库、TaskStore 或既有领域模型。
6. 为本轮新增的 Gateway、DTO、Use Case 公共方法补简短中文 Docstring 和 Java 对照；不要求给所有 Python 文件补注释。

### 验收

```bash
make test
make lint
make export-openapi
cd frontend-h5 && npm run build
git diff --check
```

- 上述命令全部返回 0。
- 临时制造一个未使用导入时，`make lint` 必须失败；撤销临时修改后重新通过。
- H5 测试真正挂载组件并触发函数，不是搜索源文件字符串。
- 在 390px 宽度人工走一次主流程，页面无横向滚动、主要按钮点击区不少于 44px；不增加真机平台或额外移动端启动脚本。
- Mock 模式断网可演示。
- 文档与实际命令一致。

---

# 5. 全部 P0 收口完成后的总体验收

只有同时满足以下条件，才允许继续 P1：

- [ ] `MOCK_MODE=true` 使用稳定 Mock，断网可以完成 H5 主流程。
- [ ] `MOCK_MODE=false` 选择真实 OpenAI-compatible Gateway，模型结果确实进入通俗解释。
- [ ] 真实网关的超时、429、非法响应能转换成明确失败，`report=None`。
- [ ] 风险 Finding 仍由程序规则决定，模型不能删掉规则命中。
- [ ] 已复现的跨句、否定和泛关键词误报全部修复。
- [ ] 结构性存款与消费贷分别使用正确的业务字段和待确认问题。
- [ ] 原文与 `taskId` 一一对应，浏览器持久存储不保存完整金融原文。
- [ ] POST 请求体、枚举和响应完整进入 OpenAPI，前端生成类型保持同步。
- [ ] H5 成功链和失败重试链至少各有一条真实组件测试。
- [ ] `make test`、`make lint`、H5 build 全部真实通过且不会吞错。
- [ ] H5 和接口响应中没有 Key、Authorization、供应商 Base URL。
- [ ] 没有重新引入 MCP 主链路、模型 HTML/Mermaid、Docker 或生产级组件。

## 6. Cursor 每项完成后的固定汇报格式

```text
完成编号：P0-RC-XX

1. 问题根因
2. 修改文件清单
3. 关键实现说明（用 Java 开发能看懂的方式）
4. 新增测试及“修复前为何失败”
5. 实际运行命令和结果
6. 是否影响 OpenAPI / H5
7. 尚未处理的问题（只能列后续编号，不能顺手扩展）
```

## 7. 代码注释规范

核心公开类和方法使用简短中文 Docstring，重点说明业务边界：

```python
class OpenAiCompatibleLlmGateway:
    """调用一个 OpenAI-compatible 模型接口。

    Java 对照：外部模型 Gateway 的实现类。
    输入：只接收应用层准备好的 Prompt，不读取 H5 参数。
    输出：已经校验过的 LlmExplanation DTO。
    业务不变量：异常必须显式失败；不得返回空结果冒充安全。
    安全边界：Key/Base URL 仅从后端 Settings 注入，不写日志。
    """
```

- 注释解释“为什么这样做”和业务不变量，不逐行翻译 Python 语法。
- 本轮新增或修改的公开边界避免未类型化的 `dict`、`list`、`Any` 和魔法字符串；不追溯重构整个知识库。
- 外部能力使用 `Protocol`；依赖通过构造函数或组合根显式传入。
- 不为了看起来像 Java 而增加没有行为的装饰器和空壳类。

---

> **最终原则：本轮不是第二次重构，而是让已经搭好的 Demo 骨架真正可信。P0 收口后再开始 P1-01。**
