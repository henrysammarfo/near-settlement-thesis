PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
.PHONY: setup fetch build rebuild test lint format check verify predictions
setup:
	python3 -m venv .venv && .venv/bin/python -m pip install -q -r requirements.txt
fetch:
	$(PY) -m settlemark fetch
build:
	$(PY) -m settlemark build
rebuild:
	sh rebuild.sh
test:
	$(PY) -m pytest
lint:
	$(PY) -m ruff check settlemark tests && $(PY) -m ruff format --check settlemark tests
format:
	$(PY) -m ruff format settlemark tests
verify:
	$(PY) -m settlemark check
predictions:
	$(PY) -m settlemark predictions --score
check: lint test verify
