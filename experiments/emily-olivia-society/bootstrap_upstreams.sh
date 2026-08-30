#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$HERE/vendor"
STANFORD_COMMIT="96854071ef4c2d79c93144c973c7820722d52bab"

python -m pip install "agentsociety2==2.8.4"

mkdir -p "$VENDOR"
if [[ ! -d "$VENDOR/stanford-genagents/.git" ]]; then
  git clone https://github.com/StanfordHCI/genagents.git "$VENDOR/stanford-genagents"
fi

git -C "$VENDOR/stanford-genagents" fetch --all --tags --prune
git -C "$VENDOR/stanford-genagents" checkout --detach "$STANFORD_COMMIT"
python -m pip install -r "$VENDOR/stanford-genagents/requirements.txt"

printf 'AgentSociety2: 2.8.4\n'
printf 'Stanford genagents: %s\n' "$STANFORD_COMMIT"
