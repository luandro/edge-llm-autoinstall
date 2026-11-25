#!/usr/bin/env bash
# One-command Google Colab GPU benchmark via the official google-colab-cli.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
exec python3 scripts/colab_benchmark_cli.py "$@"
