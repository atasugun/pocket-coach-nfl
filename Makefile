.PHONY: data dev dev-api dev-web test install

VENV := backend/.venv
PY := $(VENV)/bin/python
BACKEND_RUN := PYTHONPATH=backend $(PY)

install:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install -q --upgrade pip
	$(VENV)/bin/pip install -q -e backend -e "backend[dev]"
	cd frontend && npm install

data:
	$(BACKEND_RUN) -m pipeline.ingest
	$(BACKEND_RUN) -m pipeline.data_check
	$(BACKEND_RUN) -m pipeline.normalize
	$(BACKEND_RUN) -m pipeline.features
	$(BACKEND_RUN) -m pipeline.detect.level1
	$(BACKEND_RUN) -m pipeline.detect.level2
	$(BACKEND_RUN) -m pipeline.calibrate_level2
	$(BACKEND_RUN) -m pipeline.report_models
	$(BACKEND_RUN) -m pipeline.cost
	$(BACKEND_RUN) -m pipeline.patterns

dev:
	$(MAKE) -j2 dev-api dev-web

dev-api:
	cd backend && ../$(PY) -m uvicorn api.main:app --reload --port 8000

dev-web:
	cd frontend && npm run dev

test:
	cd backend && ../$(PY) -m pytest -q
	cd frontend && npm test -- --run
