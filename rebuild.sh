#!/usr/bin/env sh
# One command: refetch every source, recompute every number, redraw every chart, rewrite THESIS.md and the site.
set -e
cd "$(dirname "$0")"
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
$PY scripts/fetch.py
$PY scripts/build.py > /dev/null
$PY scripts/render.py
