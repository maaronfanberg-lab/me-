#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACES="$HERE/workspaces"
REPLAY_DIR="$HERE/replay"
WORKFLOW_FILE="${COMMUNITY_WORKFLOW_FILE:-emily-olivia-community-run.yml}"
ARTIFACT_NAME="${COMMUNITY_ARTIFACT_NAME:-emily-olivia-community-results}"
COMPAT_MARKER_PATH="experiments/emily-olivia-society/checkpoint-schema-v2.marker"

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
checkpoint_conclusion=""
# A Community run can preserve many valid live turns and then fail or be replaced
# later in the same conversation step. Its uploaded workspace is still a valid
# checkpoint candidate. Select completed runs by recency and let the semantic
# validator below decide whether their state is safe to restore. Checkpoint v2
# intentionally quarantines runs from before private daily plans were isolated
# from spoken-action context; preserving those old turns would faithfully carry
# planner-generated topic invention into the corrected runtime.
mapfile -t candidate_runs < <(
  gh api --method GET \
    "repos/${GITHUB_REPOSITORY}/actions/workflows/${WORKFLOW_FILE}/runs?per_page=30" \
    --jq '.workflow_runs[] | select(.status == "completed") | [.id, (.conclusion // "unknown"), .head_sha] | @tsv'
)

for candidate_info in "${candidate_runs[@]:-}"; do
  IFS=$'\t' read -r run_id run_conclusion run_head_sha <<< "$candidate_info"
  if [[ -n "$current_run" && "$run_id" == "$current_run" ]]; then
    continue
  fi
  artifact_count="$(
    gh api --method GET \
      "repos/${GITHUB_REPOSITORY}/actions/runs/${run_id}/artifacts?per_page=100" \
      --jq "[.artifacts[] | select(.name == \"$ARTIFACT_NAME\" and (.expired | not))] | length"
  )"
  if [[ "${artifact_count:-0}" -le 0 ]]; then
    continue
  fi

  # The run's checked-out commit must contain the v2 marker. This is a clean,
  # versioned compatibility boundary, not a content blacklist: pre-v2 memories
  # are left untouched in their historical artifacts but are never loaded into
  # a runtime whose speech/planning boundary has changed.
  if ! gh api --method GET \
      "repos/${GITHUB_REPOSITORY}/contents/${COMPAT_MARKER_PATH}?ref=${run_head_sha}" \
      >/dev/null 2>&1; then
    echo "Skipping checkpoint run $run_id: predates checkpoint compatibility v2."
    continue
  fi

  checkpoint_run="$run_id"
  checkpoint_conclusion="$run_conclusion"
  break
done

if [[ -z "$checkpoint_run" ]]; then
  echo "No compatible completed Community checkpoint artifact exists. Starting from clean cognition and social state."
  rm -rf "$WORKSPACES"
  rm -f "$REPLAY_DIR/social_state.json"
  mkdir -p "$REPLAY_DIR"
  cat > "$REPLAY_DIR/checkpoint_restore.json.tmp" <<JSON
{
  "mode": "checkpoint_restore",
  "restored": false,
  "source_run_id": null,
  "source_run_conclusion": null,
  "artifact": "$ARTIFACT_NAME",
  "reason": "no_compatible_checkpoint_v2",
  "social_state_restored": false
}
JSON
  mv "$REPLAY_DIR/checkpoint_restore.json.tmp" "$REPLAY_DIR/checkpoint_restore.json"
  exit 0
fi

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

gh run download "$checkpoint_run" --repo "$GITHUB_REPOSITORY" --name "$ARTIFACT_NAME" --dir "$tmp_dir"

candidate="$tmp_dir/workspaces"
if [[ ! -d "$candidate" ]]; then
  candidate="$(find "$tmp_dir" -type d -name workspaces -print -quit)"
fi
if [[ -z "${candidate:-}" || ! -d "$candidate" ]]; then
  echo "Checkpoint artifact $ARTIFACT_NAME from run $checkpoint_run contains no workspaces directory." >&2
  exit 3
fi

required_files=()
for agent in emily olivia; do
  required_files+=(
    "$candidate/$agent/scratch.json"
    "$candidate/$agent/meta.json"
    "$candidate/$agent/memory_stream/nodes.json"
    "$candidate/$agent/memory_stream/embeddings.json"
  )
done
for required in "${required_files[@]}"; do
  if [[ ! -s "$required" ]]; then
    echo "Checkpoint is incomplete: missing or empty $required" >&2
    exit 4
  fi
done

python3 - "${required_files[@]}" <<'PY'
import json, sys
for raw in sys.argv[1:]:
    with open(raw, encoding="utf-8") as handle:
        json.load(handle)
print("Checkpoint workspace JSON validated.")
PY

social_state="$(find "$tmp_dir" -type f -path '*/replay/social_state.json' -print -quit)"

# JSON validity is not enough. Early runs contained syntactically valid
# customer-service boilerplate, malformed reflection JSON, and short attractor loops that
# repeatedly dragged Emily and Olivia back into unusable dialogue. Never restore those.
if ! python3 - "$candidate" "${social_state:-}" <<'PY'
import json
import pathlib
import re
import sys

workspace = pathlib.Path(sys.argv[1])
social = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else None

patterns = [
    ("template_junk", re.compile(r'[\{\[]?\s*["\']?utter(?:ance)?["\']?\s*[:=]|\[\s*input\s*\]\s*:', re.I)),
    ("service_language", re.compile(
        r'how\s+can\s+i\s+(?:help|assist)\s+you|feel\s+free\s+to\s+ask|'
        r'need\s+(?:any\s+)?(?:further\s+)?assistance|'
        r'i(?:\'m|\s+am)\s+sorry[^.]{0,100}(?:can(?:not|\'t)|unable)\s+(?:assist|help|fulfill)|'
        r'i\s+can(?:not|\'t)\s+(?:assist|help|fulfill)(?:\s+with)?\s+(?:this|that|your)\s+request|'
        r'(?:i\s+am|i\'m)\s+(?:currently\s+)?in\s+a\s+(?:two-person\s+)?community|'
        r'asking\s+about\s+my\s+last\s+update|as\s+an\s+ai',
        re.I,
    )),
    ("dead_end_attractor", re.compile(
        r'^\s*i(?:\'m|\s+am)\s+not\s+sure\s+what\s+to\s+say\.?\s*$|'
        r'^\s*i(?:\'ve|\s+have)\s+been\s+trying(?:\.\s*i(?:\'ve|\s+have)\s+been\s+trying)*\.?\s*$',
        re.I,
    )),
]

def classify(text: str):
    text = str(text or "").strip()
    if not text:
        return None
    if text.startswith("```"):
        return "malformed_reflection_payload"
    if re.match(r'^\{\s*["\']reflection["\']\s*:', text, re.I | re.S):
        return "malformed_reflection_payload"
    for name, pattern in patterns:
        if pattern.search(text):
            return name
    return None

bad = []
for agent in ("emily", "olivia"):
    nodes_path = workspace / agent / "memory_stream" / "nodes.json"
    nodes = json.loads(nodes_path.read_text(encoding="utf-8"))
    if not isinstance(nodes, list):
        raise SystemExit(f"Unexpected memory schema for {agent}")
    for node in nodes:
        reason = classify(node.get("content", ""))
        if reason:
            bad.append((agent, reason, str(node.get("content", ""))[:180]))

if social and social.is_file():
    state = json.loads(social.read_text(encoding="utf-8"))
    for inbox in (state.get("inboxes") or {}).values():
        if not isinstance(inbox, list):
            continue
        for message in inbox:
            reason = classify(message.get("content", ""))
            if reason:
                bad.append(("social_state", reason, str(message.get("content", ""))[:180]))

if bad:
    print(f"Checkpoint semantic contamination detected ({len(bad)} bad memories/messages); refusing restore.", file=sys.stderr)
    for source, reason, preview in bad[:8]:
        print(f"  {source}: {reason}: {preview!r}", file=sys.stderr)
    raise SystemExit(1)

print("Checkpoint semantic dialogue validation passed.")
PY
then
  echo "Prior checkpoint is semantically contaminated; starting Emily and Olivia from clean cognition instead."
  rm -rf "$WORKSPACES"
  rm -f "$REPLAY_DIR/social_state.json"
  mkdir -p "$REPLAY_DIR"
  cat > "$REPLAY_DIR/checkpoint_restore.json.tmp" <<JSON
{
  "mode": "checkpoint_restore",
  "restored": false,
  "source_run_id": $checkpoint_run,
  "source_run_conclusion": "$checkpoint_conclusion",
  "artifact": "$ARTIFACT_NAME",
  "reason": "semantic_dialogue_contamination",
  "social_state_restored": false
}
JSON
  mv "$REPLAY_DIR/checkpoint_restore.json.tmp" "$REPLAY_DIR/checkpoint_restore.json"
  exit 0
fi

social_restored=false
if [[ -n "${social_state:-}" && -s "$social_state" ]]; then
  python3 - "$social_state" <<'PY'
import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    state = json.load(handle)
if not isinstance(state, dict) or state.get("version") != 1:
    raise SystemExit("Invalid social state version")
inboxes = state.get("inboxes")
if not isinstance(inboxes, dict) or not all(isinstance(inboxes.get(key, []), list) for key in ("1", "2")):
    raise SystemExit("Invalid social state inbox schema")
print("Checkpoint social state JSON validated.")
PY
  social_restored=true
fi

new_workspaces="$HERE/.workspaces.restore.$$"
rm -rf "$new_workspaces"
cp -a "$candidate" "$new_workspaces"
rm -rf "$WORKSPACES"
mv "$new_workspaces" "$WORKSPACES"

mkdir -p "$REPLAY_DIR"
if [[ "$social_restored" == true ]]; then
  cp "$social_state" "$REPLAY_DIR/social_state.json.tmp"
  mv "$REPLAY_DIR/social_state.json.tmp" "$REPLAY_DIR/social_state.json"
else
  rm -f "$REPLAY_DIR/social_state.json"
fi

cat > "$REPLAY_DIR/checkpoint_restore.json.tmp" <<JSON
{
  "mode": "checkpoint_restore",
  "restored": true,
  "source_run_id": $checkpoint_run,
  "source_run_conclusion": "$checkpoint_conclusion",
  "artifact": "$ARTIFACT_NAME",
  "social_state_restored": $social_restored
}
JSON
mv "$REPLAY_DIR/checkpoint_restore.json.tmp" "$REPLAY_DIR/checkpoint_restore.json"

echo "Restored Emily + Olivia workspaces from valid checkpoint run $checkpoint_run (conclusion=$checkpoint_conclusion)."
echo "Persistent social state restored: $social_restored"
