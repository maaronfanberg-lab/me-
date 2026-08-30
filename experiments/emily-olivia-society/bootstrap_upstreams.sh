#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$HERE/vendor"
AS_VENV="$HERE/.venv-agentsociety"
STANFORD_VENV="$HERE/.venv-stanford"
STANFORD_COMMIT="96854071ef4c2d79c93144c973c7820722d52bab"

python3 -m venv "$AS_VENV"
"$AS_VENV/bin/python" -m pip install --upgrade pip
"$AS_VENV/bin/python" -m pip install "agentsociety2==2.8.4"

mkdir -p "$VENDOR"
if [[ ! -d "$VENDOR/stanford-genagents/.git" ]]; then
  git clone https://github.com/StanfordHCI/genagents.git "$VENDOR/stanford-genagents"
fi

git -C "$VENDOR/stanford-genagents" fetch --all --tags --prune
git -C "$VENDOR/stanford-genagents" checkout --detach "$STANFORD_COMMIT"

python3 -m venv "$STANFORD_VENV"
"$STANFORD_VENV/bin/python" -m pip install --upgrade pip
"$STANFORD_VENV/bin/python" -m pip install -r "$VENDOR/stanford-genagents/requirements.txt"

printf 'AgentSociety2: 2.8.4 -> %s\n' "$AS_VENV"
printf 'Stanford genagents: %s -> %s\n' "$STANFORD_COMMIT" "$STANFORD_VENV"
printf 'Initialize cognition with: %s init_cognition.py\n' "$STANFORD_VENV/bin/python"
printf 'Initialize society with: %s run.py\n' "$AS_VENV/bin/python"
