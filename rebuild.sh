#!/usr/bin/env sh
# One command: refetch every source, validate it, recompute every number, redraw every chart,
# and rewrite THESIS.md and the live page. Pass --no-cache to ignore the local HTTP cache.
set -eu
cd "$(dirname "$0")"
PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python
exec "$PY" -m settlemark rebuild "$@"
