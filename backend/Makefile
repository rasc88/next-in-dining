VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
UVICORN := $(VENV)/bin/uvicorn
PYTEST := $(VENV)/bin/pytest

.DEFAULT_GOAL := help

.PHONY: help install run test clean

help:
	@echo "make install  - create the virtualenv and install dependencies"
	@echo "make run      - start the API with auto-reload on http://localhost:8000"
	@echo "make test     - run the test suite"
	@echo "make clean    - remove the virtualenv and cached files"

$(PYTHON):
	python3 -m venv $(VENV)

install: $(PYTHON)
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

run: $(PYTHON)
	$(UVICORN) app.main:app --reload

test: $(PYTHON)
	$(PYTEST)

clean:
	rm -rf $(VENV) .pytest_cache waitlist_backend.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
