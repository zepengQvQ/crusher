# backend-python/

后端服务（正式 Demo 用这一套）。

| 内容 | 白话 |
|------|------|
| `app/` | 业务代码（接请求、跑分析、规则） |
| `pyproject.toml` | 这个 Python 项目叫什么、依赖什么 |
| `requirements.lock` | 依赖版本锁死，避免大家装的不一样 |
| `.venv/` | 本机虚拟环境（别提交到 git） |

启动见仓库根目录 `README.md`，或在本目录：

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

更细的子目录说明见各自 `project.md`。
