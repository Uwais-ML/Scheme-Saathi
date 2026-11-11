# Makefile – Scheme Saathi
PYTHON := .venv/bin/python
UVICORN := .venv/bin/uvicorn
PIP := .venv/bin/pip

.PHONY: install ingest test eval run dev help

help:
	@echo "Scheme Saathi – make targets:"
	@echo "  install   Install all dependencies into .venv"
	@echo "  ingest    Run RAG ingestion (builds chroma_db/)"
	@echo "  test      Run all unit + integration tests"
	@echo "  eval      Run evaluation suite (CI gate)"
	@echo "  run       Start production server on :8000"
	@echo "  dev       Start dev server with auto-reload"

install:
	python3 -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

ingest:
	$(PYTHON) -m rag.ingest

test:
	.venv/bin/pytest tests/ -v

eval:
	$(PYTHON) -m tests.evals.run_all

run:
	$(UVICORN) api.main:app --host 0.0.0.0 --port 8000

dev:
	$(UVICORN) api.main:app --host 0.0.0.0 --port 8000 --reload
