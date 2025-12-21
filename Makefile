PYTHON ?= python
PIP ?= $(PYTHON) -m pip
FRONTEND_DIR := frontend
BACKEND_REQ := backend/requirements.txt

.PHONY: setup test build run eval deploy

setup:
	$(PYTHON) -m pip install -r $(BACKEND_REQ)
	cd $(FRONTEND_DIR) && npm install

test:
	$(PYTHON) -m pytest -q
replay:
	$(PYTHON) runtime/replay/replay_runner.py $(TASK_ID)

build:
	cd $(FRONTEND_DIR) && npm run build

run:
	$(PYTHON) scripts/run_backend.py

eval:
	$(PYTHON) scripts/run_phase7_evaluation.py

deploy:
	docker compose up --build
























