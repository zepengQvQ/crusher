# app/

后端主代码入口。

- `main.py`：启动网站服务（FastAPI）
- `composition_root.py`：把各模块 `new` 出来、接在一起（类似 Spring 配置类）

| 子目录 | 白话 |
|--------|------|
| `interfaces/` | 对外：收 HTTP 请求、回 JSON |
| `application/` | 业务流程：创建任务、在后台跑分析 |
| `domain/` | 核心业务：数据结构、规则（尽量不碰网页框架） |
| `infrastructure/` | 落地实现：读文件、假/真大模型、内存存任务 |
| `config/` | 读根目录 `.env` |
| `shared/` | 日志等小工具 |
