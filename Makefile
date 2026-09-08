.PHONY: dev-api dev-h5 test-api test-p0-01 test-p0-05 lint install

install:
	cd backend-python && pip install -e ".[dev]"
	cd frontend-h5 && npm install

dev-api:
	cd backend-python && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-h5:
	cd frontend-h5 && npm run dev

test-api:
	cd backend-python && ../backend-python/.venv/bin/python -m unittest discover -s ../tests/api -v

export-openapi:
	backend-python/.venv/bin/python scripts/export_openapi.py

test-p0-01:
	python tests/p0_01/run_p0_01.py --only golden

test-p0-05:
	backend-python/.venv/bin/python -m unittest discover -s tests/p0_05 -v
	backend-python/.venv/bin/python -m unittest tests.p0_01.test_negation_regression -v

lint:
	cd backend-python && ruff check app && pyright app || true
