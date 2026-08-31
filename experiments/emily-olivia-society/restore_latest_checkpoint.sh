#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACES="$HERE/workspaces"
REPLAY_DIR="$HERE/replay"
WORKFLOW_FILE="${COMMUNITY_WORKFLOW_FILE:-emily-olivia-community-run.yml}"
ARTIFACT_NAME="${COMMUNITY_ARTIFACT_NAME:-emily-olivia-community-results}"

if [[ -z "${GITHUB_REPOSITORY:-}" ]]; then
  echo "GITHUB_REPOSITORY is required to restore a checkpoint." >&2
  exit 2
fi

if [[ -z "${GH_TOKEN:-}" ]]; then
  echo "GH_TOKEN is required to restore a checkpoint." >&2
  exit 2
fi

current_run="${GITHUB_RUN_ID:-}"
checkpoint_run=""

mapfile -t candidate_runs < <(
  gh api --method GET \
    "repos/${GITHUB_REPOSITORY}/actions/workflows/${WORKFLOW_FILE}/runs?per_page=30" \
    --jq '.workflow_runs[] | select(.status == "completed") | .id'
)

for run_id in "${candidate_runs[@]:-}"; do
  if [[ -n "$current_run" && "$run_id" == "$current_run" ]]; then
    continue
  fi

  artifact_count="$(
    gh api --method GET \
      "repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}/artifacts?per_page=100" \
      --jq "[.artifacts[] | select(.name == \"$ARTIFACT_NAME\" and (.expired | not))] | length"
  )"

  if [[ "${artifact_count:-0}" -gt 0 ]]; then
    checkpoint_run="$run_id"
    break
  fi
done

if [[ -z "$checkpoint_run" ]]; then
  echo "No prior community checkpoint artifact exists. Fresh initialization is allowed."
  exit 0
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

gh run download "$checkpoint_run" \
  --repo "$GITHUB_REPOSITORY" \
  --name "$ARTIFACT_NAME" \
  --dir "$tmp_dir"

candidate="$tmp_dir/workspaces"
if [[ ! -d "$candidate" ]]; then
  candidate="$(find "$tmp_dir" -type d -name workspaces -print -quit)"
fi

if [[ -z "${candidate:-}" || ! -d "$candidate" ]]; then
  echo "Checkpoint artifact $ARTIFACT_NAME from run $checkpoint_run contains no workspaces directory." >&2
  exit 3
fi

for agent in emily olivia; do
  for required in \
    "$candidate/$agent/scratch.json" \
    "$candidate/$agent/meta.json" \
    "$candidate/$agent/memory_stream/nodes.json" \
    "$candidate/$agent/memory_stream/embeddings.json"; do
    if [[ ! -s "$required" ]]; then
      echo "Checkpoint is incomplete: missing or empty $required" >&2
      exit 4
    fi
  done
done

rm -rf "$WORKSPACES"
cp -a "$candidate" "$WORKSPACES"

mkdir -p "$REPLAY_DIR"
social_state="$(find "$tmp_dir" -type f -path '*/replay/social_state.json' -print -quit)"
if [[ -n "${social_state:-}" && -s "$social_state" ]]; then
  cp "$social_state" "$REPLAY_DIR/social_state.json"
  social_restored=true
else
  rm -f "$REPLAY_DIR/social_state.json"
  social_restored=false
fi

cat > "$REPLAY_DIR/checkpoint_restore.json" <<JSON
{
  "mode": "checkpoint_restore",
  "restored": true,
  "source_run_id": $checkpoint_run,
  "artifact": "$ARTIFACT_NAME",
  "social_state_restored": $social_restored
}
JSON

echo "Restored Emily + Olivia workspaces from valid checkpoint run $checkpoint_run."
echo "Persistent social state restored: $social_restored"
