# 金融话术粉碎机（Demo）

把金融条款粘贴进去，得到通俗解释、关键参数和风险发现。

> 当前主路径：**Vue3 H5 + Python FastAPI**。不用 Docker，本机两个终端启动即可。

## 怎么启动

1. 复制环境变量（密钥只放本机，不要写进网页）：

```bash
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY（现在演示模式可不填也能跑通 mock）
```

2. 启动后端（接口文档：http://localhost:8000/docs）

```bash
cd backend-python
python3.11 -m venv .venv   # 首次
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

3. 再开一个终端启动网页（http://localhost:5173）

```bash
cd frontend-h5
npm install   # 首次
npm run dev
```

也可看：`scripts/dev.sh`

## 现在做到哪了

| 编号 | 内容 |
|------|------|
| P0-01 | 范围冻结、样例与回归题 |
| P0-02 | 前后端分开 |
| P0-03 | 密钥只在服务端；失败不能显示成「没风险」 |
| P0-04 | 报告字段用强类型定死 |

首版对外只演示：**结构性存款**、**借贷**。详见 [`docs/demo-scope.md`](docs/demo-scope.md)。

## 目录说明（人话）

```text
frontend-h5/        手机网页
backend-python/     处理请求的 Python 服务
knowledge/          金融知识 JSON
docs/               说明与整改清单
contracts/          接口 OpenAPI 快照
tests/              测试与样例
legacy/             旧 Streamlit，仅对照，不再加功能
```

## 常用命令

```bash
# 导出 OpenAPI，并更新前端 generated-types.js
make export-openapi

# 跑接口相关测试
make test-api

# P0-01 金标
python tests/p0_01/run_p0_01.py --only golden
```

## 旧版对照（可选）

```bash
cd legacy
# 需自行安装 streamlit 等旧依赖
streamlit run streamlit_app.py
```

旧版不作为 Demo 主入口；密钥也不要指望在网页侧边栏填写。

## 整改文档

- 清单（以 docs 这份为准）：[`docs/金融话术粉碎机-整改实施清单.md`](docs/金融话术粉碎机-整改实施清单.md)
- Cursor 约束：[`cursor.md`](cursor.md)

## 免责声明

仅供学习参考，不构成投资建议；本 Demo 不进行用户适当性评估。
