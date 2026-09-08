# crusher-backend

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
# 可选锁定版本：
# pip install -r requirements.lock
uvicorn app.main:app --reload --port 8000
```

从仓库根目录也可用：`bash scripts/dev.sh` / `make setup`。
