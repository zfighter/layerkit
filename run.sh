#!/usr/bin/env bash
# One-shot setup + test + demo + batch-card runner for layerkit.
#
# Usage:
#   ./run.sh                 # setup, run tests, run demo
#   ./run.sh test              # setup + tests only
#   ./run.sh demo                # setup + demo only
#   ./run.sh cards                 # setup + batch-generate cards from origin_cards/mapping.txt
#   ./run.sh cards --scale 2         # extra args are forwarded to batch_cards.py
set -euo pipefail
cd "$(dirname "$0")"

MODE="${1:-all}"
[ $# -gt 0 ] && shift || true

if [ ! -d ".venv" ]; then
    echo "==> Creating virtual environment (.venv)"
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> Installing dependencies"
pip install -q -e ".[dev]"

if [ "$MODE" = "test" ] || [ "$MODE" = "all" ]; then
    echo "==> Running tests"
    pytest -v
fi

if [ "$MODE" = "demo" ] || [ "$MODE" = "all" ]; then
    echo "==> Running demo"
    python examples/demo.py
fi

if [ "$MODE" = "cards" ]; then
    echo "==> Generating cards from origin_cards/mapping.txt"
    python batch_cards.py "$@"
fi

echo "==> Done"
