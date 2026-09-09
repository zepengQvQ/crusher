.PHONY: setup demo dev-api dev-h5 test test-api test-p0-01 test-p0-05 test-p0-06 test-p0-07 test-p0-08 test-p0-09 test-p0-rc-01 test-p0-rc-02 test-p0-rc-03 test-p0-rc-04 test-p0-rc-05 test-p0-rc-06 test-p0-rc-07 test-p0-rc-08 test-p0-rc-09 test-p0-rc-10 test-p0-rc-11 test-p0-rc-12 test-p1-01 test-p1-02 test-p1-03 test-p1-04 test-p1-06 lint install export-openapi

setup:
	bash scripts/dev.sh

demo:
	@echo "1) make setup（若尚未安装）"
	@echo "2) 终端1: source backend-python/.venv/bin/activate && uvicorn app.main:app --reload --app-dir backend-python --port 8000"
	@echo "3) 终端2: cd frontend-h5 && npm run dev"
	@echo "4) 打开 http://localhost:5173 点示例分析；可用「模拟模型超时」看错误页"
	@echo "5) make test"
	@echo "样例说明: docs/demo-支持范围与样例.md"
	@echo "HTTP 示例: docs/http/示例-分析接口.http"

install: setup

dev-api:
	cd backend-python && ../backend-python/.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-h5:
	cd frontend-h5 && npm run dev

test:
	bash scripts/run_all_tests.sh

test-api:
	cd backend-python && MOCK_MODE=true ../backend-python/.venv/bin/python -m unittest discover -s ../tests/api -v

export-openapi:
	cd backend-python && ../backend-python/.venv/bin/python -c "import app" >/dev/null 2>&1 || pip install -e ".[dev]"
	PYTHONPATH=backend-python backend-python/.venv/bin/python scripts/export_openapi.py

test-p0-01:
	python tests/p0_01/run_p0_01.py --only golden

test-p0-05:
	backend-python/.venv/bin/python -m unittest discover -s tests/p0_05 -v
	backend-python/.venv/bin/python -m unittest tests.p0_01.test_negation_regression -v

test-p0-06:
	backend-python/.venv/bin/python -m unittest discover -s tests/p0_06 -v

test-p0-07:
	backend-python/.venv/bin/python -m unittest discover -s tests/p0_07 -v

test-p0-08:
	backend-python/.venv/bin/python -m unittest discover -s tests/p0_08 -v

test-p0-09:
	backend-python/.venv/bin/python -m unittest discover -s tests/p0_09 -v

test-p0-rc-01:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p0_rc_01 -v

test-p0-rc-02:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p0_rc_02 -v

test-p0-rc-03:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p0_rc_03 -v

test-p0-rc-04:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p0_rc_04 -v

test-p0-rc-05:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p0_rc_05 -v

lint:
	cd backend-python && .venv/bin/ruff check app && .venv/bin/pyright app

test-p0-rc-06:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p0_rc_06 -v
	cd frontend-h5 && npm test

test-p0-rc-07:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p0_rc_07 -v

test-p0-rc-08:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p0_rc_08 -v

test-p0-rc-09:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p0_rc_09 -v
	cd frontend-h5 && npm test -- analysis-scope.spec.js

test-p0-rc-10:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p0_rc_10 -v

test-p0-rc-11:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p0_rc_11 -v
	cd frontend-h5 && npm test -- task-binding.spec.js

test-p0-rc-12:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p0_rc_12 -v
	cd frontend-h5 && npm run typecheck

test-p1-01:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p1_01 -v

test-p1-02:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p1_02 -v

test-p1-03:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p1_03 -v

test-p1-04:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p1_04 -v

test-p1-06:
	MOCK_MODE=true backend-python/.venv/bin/python -m unittest discover -s tests/p1_06 -v
