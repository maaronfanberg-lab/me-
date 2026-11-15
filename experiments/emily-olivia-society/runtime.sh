#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

if [[ ! -x .venv-agentsociety/bin/python || ! -x .venv-stanford/bin/python ]]; then
  bash bootstrap_upstreams.sh
fi

if [[ ! -f workspaces/emily/scratch.json || ! -f workspaces/olivia/scratch.json ]]; then
  .venv-stanford/bin/python init_cognition.py
fi

exec .venv-agentsociety/bin/python run.py
