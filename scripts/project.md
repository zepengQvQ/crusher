# scripts/

本机开发用的脚本（不用 Docker）。

| 脚本 | 白话 |
|------|------|
| `dev.sh` | 准备配置、虚拟环境、依赖，并打印「开两个终端」的启动命令 |
| `run_all_tests.sh` | `make test` 真正执行的那套测试 |
| `export_openapi.py` | 改完接口后：导出接口说明书 + 更新前端类型 |

常用：`bash scripts/dev.sh`，或根目录 `make setup` / `make test`。
