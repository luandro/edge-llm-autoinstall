#!/usr/bin/env bash
# Reproducible, unprivileged model comparisons. No sudo or system service changes.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
for arg in "$@"; do
  if [[ "$arg" == '--dry-run' || "$arg" == '--server-url' ]]; then
    exec python3 scripts/benchmark_suite.py "$@"
  fi
done
PY=python3
if ! python3 -c 'import huggingface_hub' 2>/dev/null; then
  if [[ ! -x .venv-benchmark/bin/python ]]; then
    python3 -m venv .venv-benchmark || {
      echo 'python3-venv is needed. Install it or run: python3 -m pip install --user huggingface_hub' >&2
      exit 1
    }
  fi
  PY=.venv-benchmark/bin/python
  if ! "$PY" -c 'import huggingface_hub' 2>/dev/null; then
    echo 'Installing huggingface_hub in project-local venv (no sudo) ...'
    "$PY" -m pip install -q 'huggingface_hub>=0.31,<2'
  fi
fi
exec "$PY" scripts/benchmark_suite.py "$@"