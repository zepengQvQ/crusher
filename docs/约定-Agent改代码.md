# 约定：改代码（当前有效）

审查基线：`origin/main` 最新提交。

## 先读什么

1. 用户本轮指令（指定文件 / 行为 / 编号时以用户为准）。
2. [`范围-Demo支持与样例.md`](范围-Demo支持与样例.md) —— 做什么、不做什么。
3. [`地图-代码与请求链路.md`](地图-代码与请求链路.md) —— 改哪里。
4. 相关现有测试与实现。

[`archive/`](archive/) 里的 P0/P1/P2 清单**只查阅、不默认继续执行**；仅当用户点名某编号时才按该清单验收。

## 技术边界（Demo）

- 前端：Vue3 + Vant H5；服务端：Python + FastAPI。
- **不**引入 Docker、微服务、生产级中间件、Java 服务端。
- **不**恢复已删除的 `legacy/`；**不**把可选 MCP 挂进 H5 / FastAPI 主链路（见 [`说明-MCP本地.md`](说明-MCP本地.md)）。
- Python 须让 Java 开发易读：强类型、Pydantic 边界、Protocol、Use Case 类、构造函数注入、中文业务 Docstring；禁止仿 Java 的自定义魔法装饰器。

## 编码习惯（硬约束）

### 分层落点

| 层 | 目录 | 只允许 |
|----|------|--------|
| HTTP | `interfaces/http/` | 入参校验、DTO 组装、调用 Use Case |
| 应用 | `application/` | 编排流程、事务边界（本 Demo 即任务生命周期） |
| 领域 | `domain/` | 规则、证据、发布门禁、模型 |
| 基础设施 | `infrastructure/` | 文件 / LLM / 任务存储等 IO |
| 接线 | `composition_root.py` | `new` 并注入依赖 |

禁止在 `routes.py` 写关键词/否定/数值规则；禁止在 Gateway 里做业务裁决。

### 权威类型名（新代码）

| 用这个 | 不要新用（仅为兼容保留） |
|--------|--------------------------|
| `CreateAnalysisRequest` | `AnalyzeTextRequest` |
| `LlmAnalysisDraft` | `LlmExplanation` |
| `is_target_negated` | `is_negated_near` |

禁止再增加「旧名 = 新名」兼容别名。权威模块以现有定义处为准（如报告请求在 `domain/models/report.py`）。

### 错误与发布

- 对外 `error_code` 优先使用 `ErrorCode`（或项目已有枚举）；禁止随手魔法字符串。
- 报告能否展示只信领域层的 `publication`（`publish` / `publish_partial` / `clarify` / `refuse`）；HTTP/H5 **不得**自行拼装「看起来成功」。
- 失败必须显式：禁止静默 fallback，禁止空 findings / 空报告冒充「未发现风险」。

### 证据与事实

- 每条 Finding 必须能落到原文证据（quote + span）。
- 原文未写 → `not_disclosed`；禁止用行业常识填当前合同字段。
- 产品级用 `product_risk_grade`，发现级用 `finding_severity`；禁止混用同一个展示名 `risk_level`。

### 测试落点

- 阶段能力：`tests/p0_*` / `p0_rc_*` / `p1_*` / `p2_*`（按现有编号习惯；缺目录时先问再新建）。
- 横切契约：`tests/api/`；夹具优先 `tests/fixtures/`。
- 改打包/文档路径时同步 `tests/p0_09`；改 API 后 `make export-openapi` 并跑相关测。

### 前端习惯

- 页面 `*Page.vue`，可复用块放 `components/`；HTTP **只**走 `frontend-h5/src/api/client.js`。
- **禁止**手改 `generated-types.js`（由导出生成）。
- H5 **不**展示、不接收 API Key / `base_url`。

### 五条硬禁令

1. 不扩产品类型 / 主链路能力，除非先改 [`范围-Demo支持与样例.md`](范围-Demo支持与样例.md) 并获用户确认。
2. 不手改 `frontend-h5/src/api/generated-types.js`。
3. 不在 `routes.py` 写领域规则。
4. 不新增兼容别名；不静默吞错。
5. 不提交 `.env`；不恢复 `legacy/`。

## 执行要求

1. 先阅读相关代码与测试，列出准备修改的文件。
2. 先补能复现问题的失败测试，再改实现。
3. 不做超出本任务的顺手重构；保留无关的现有改动。
4. 错误显式返回（见上文「错误与发布」）。
5. 改 API 时同步：Pydantic Schema、`contracts/openapi.json`（`make export-openapi`）、前端类型、`docs/api` / `docs/http` 示例。
6. 跑相关测试；有把握时跑 `make lint` / `make test`。
7. 用户要求提交时再 commit；禁止提交 `.env`。推送按用户明确要求。
8. 交付说明：修改文件、行为变化、测试结果、剩余风险、建议下一步（**不要**编造「下一清单编号」）。
9. 对用户用简体中文；代码标识、路径、API、类型名保持英文原样。

结束条件：用户验收标准；若用户点名归档清单编号，则以该编号下的「验收」为准。

## 改文档时

遵守 [`project.md`](project.md) 命名规则：

| 类型 | 语法 |
|------|------|
| 现行说明 | `类别-简述.md`（类别仅：`约定` / `范围` / `地图` / `说明`） |
| 接口示例 | `示例-简述.json` 或 `.http` |
| 历史清单 | `archive/阶段-简述.md` |

文件名以中文为主。仅允许这些专有词出现在文件名中：`Demo`、`MCP`、`Agent`、`P0`/`P1`/`P2`。正文用中文；代码标识、路径、API、类型名保持英文原样。
