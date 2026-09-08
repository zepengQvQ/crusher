# Java → Python 代码地图（Demo）

从「接口」一路点到「规则」，大约这样找：

| 你想找的东西 | 打开这个文件 | Java 对照 |
|---|---|---|
| 路由 / Controller | `backend-python/app/interfaces/http/routes.py` | `@RestController` |
| 用例编排 | `backend-python/app/application/analyze_text.py` | Application Service |
| 依赖装配 | `backend-python/app/composition_root.py` | `@Configuration` / Bean |
| 接口（端口） | `backend-python/app/domain/ports/protocols.py` | interface |
| 规则引擎 | `backend-python/app/domain/rules/engine.py` | Domain Service |
| 事实抽取 | `backend-python/app/domain/rules/fact_extractor.py` | Domain Service |
| 证据校验 | `backend-python/app/domain/rules/evidence.py` | Domain Service |
| 知识库文件适配 | `backend-python/app/infrastructure/knowledge/local_files.py` | Repository Impl |
| LLM Mock | `backend-python/app/infrastructure/llm/mock_gateway.py` | Gateway Impl |
| 配置 | `backend-python/app/config/settings.py` | `@ConfigurationProperties` |
| H5 路由 | `frontend-h5/src/router/index.js` | 前端 Router |

请求顺序见 [`request-flow.md`](request-flow.md)。
