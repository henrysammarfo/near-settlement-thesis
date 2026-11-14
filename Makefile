PY ?= $(shell [ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)
.PHONY: setup fetch build rebuild test
setup:
	python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt
fetch:
	$(PY) scripts/fetch.py
build:
	$(PY) scripts/build.py > /dev/null && $(PY) scripts/render.py
rebuild:
	sh rebuild.sh
test:
	$(PY) -m pytest -q
