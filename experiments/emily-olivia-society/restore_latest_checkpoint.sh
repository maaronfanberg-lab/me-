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

reset_clean() {
  local reason="$1"
  rm -rf "$WORKSPACES"
  mkdir -p "$REPLAY_DIR"
  rm -f \
    "$REPLAY_DIR/social_state.json" \
    "$REPLAY_DIR/checkpoint_session.json" \
    "$REPLAY_DIR/community_session.json" \
    "$REPLAY_DIR/community_session.jsonl" \
    "$REPLAY_DIR/community_session_error.json"
  cat > "$REPLAY_DIR/checkpoint_restore.json.tmp" <<JSON
{
  "mode": "checkpoint_restore",
  "restored": false,
  "source_run_id": null,
  "source_run_conclusion": null,
  "artifact": "$ARTIFACT_NAME",
  "reason": "$reason",
  "social_state_restored": false
}
JSON
  mv "$REPLAY_DIR/checkpoint_restore.json.tmp" "$REPLAY_DIR/checkpoint_restore.json"
}

validate_semantics() {
  local workspace="$1"
  local social_state="${2:-}"
  python3 - "$workspace" "$social_state" <<'PY'
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
    inboxes = state.get("inboxes") if isinstance(state, dict) else None
    if not isinstance(state, dict) or state.get("version") != 1 or not isinstance(inboxes, dict):
        raise SystemExit("Invalid social state schema")
    if not all(isinstance(inboxes.get(key, []), list) for key in ("1", "2")):
        raise SystemExit("Invalid social state inbox schema")
    for inbox in inboxes.values():
        if not isinstance(inbox, list):
            continue
        for message in inbox:
            reason = classify(message.get("content", ""))
            if reason:
                bad.append(("social_state", reason, str(message.get("content", ""))[:180]))

if bad:
    print(f"Checkpoint semantic contamination detected ({len(bad)} bad memories/messages).", file=sys.stderr)
    for source, reason, preview in bad[:8]:
        print(f"  {source}: {reason}: {preview!r}", file=sys.stderr)
    raise SystemExit(1)
print("Checkpoint structural memory validation passed.")
PY
}

current_run="${GITHUB_RUN_ID:-}"
checkpoint_run=""
checkpoint_conclusion=""
candidate=""
social_state=""
checkpoint_summary=""
checkpoint_history=""
checkpoint_message_count=0

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

# Only a successfully completed workflow is eligible to become durable cognition.
# Cancelled/failed artifacts remain diagnostic evidence, never continuity state.
mapfile -t candidate_runs < <(
  gh api --method GET \
    "repos/${GITHUB_REPOSITORY}/actions/workflows/${WORKFLOW_FILE}/runs?per_page=30" \
    --jq '.workflow_runs[] | select(.status == "completed" and .conclusion == "success") | [.id, .conclusion, .head_sha] | @tsv'
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

  if ! gh api --method GET \
      "repos/${GITHUB_REPOSITORY}/contents/${COMPAT_MARKER_PATH}?ref=${run_head_sha}" \
      >/dev/null 2>&1; then
    echo "Skipping checkpoint run $run_id: predates checkpoint compatibility v2."
    continue
  fi

  run_dir="$tmp_dir/run-$run_id"
  mkdir -p "$run_dir"
  if ! gh run download "$run_id" --repo "$GITHUB_REPOSITORY" --name "$ARTIFACT_NAME" --dir "$run_dir"; then
    echo "Skipping checkpoint run $run_id: artifact download failed."
    rm -rf "$run_dir"
    continue
  fi

  workspace_candidate="$run_dir/workspaces"
  if [[ ! -d "$workspace_candidate" ]]; then
    workspace_candidate="$(find "$run_dir" -type d -name workspaces -print -quit)"
  fi
  if [[ -z "${workspace_candidate:-}" || ! -d "$workspace_candidate" ]]; then
    echo "Skipping checkpoint run $run_id: artifact contains no workspaces directory."
    rm -rf "$run_dir"
    continue
  fi

  required_files=()
  for agent in emily olivia; do
    required_files+=(
      "$workspace_candidate/$agent/scratch.json"
      "$workspace_candidate/$agent/meta.json"
      "$workspace_candidate/$agent/memory_stream/nodes.json"
      "$workspace_candidate/$agent/memory_stream/embeddings.json"
    )
  done

  incomplete=false
  for required in "${required_files[@]}"; do
    if [[ ! -s "$required" ]]; then
      echo "Skipping checkpoint run $run_id: missing or empty $required"
      incomplete=true
      break
    fi
  done
  if [[ "$incomplete" == true ]]; then
    rm -rf "$run_dir"
    continue
  fi

  if ! python3 - "${required_files[@]}" <<'PY'
import json, sys
for raw in sys.argv[1:]:
    with open(raw, encoding="utf-8") as handle:
        json.load(handle)
PY
  then
    echo "Skipping checkpoint run $run_id: workspace JSON is invalid."
    rm -rf "$run_dir"
    continue
  fi

  replay_candidate="$(find "$run_dir" -type d -name replay -print -quit)"
  summary_candidate=""
  error_candidate=""
  social_candidate=""
  if [[ -n "${replay_candidate:-}" && -d "$replay_candidate" ]]; then
    summary_candidate="$replay_candidate/community_session.json"
    error_candidate="$replay_candidate/community_session_error.json"
    social_candidate="$replay_candidate/social_state.json"
  fi
  if [[ -z "$summary_candidate" || ! -s "$summary_candidate" ]]; then
    echo "Skipping checkpoint run $run_id: artifact contains no completed session summary."
    rm -rf "$run_dir"
    continue
  fi

  if ! validate_semantics "$workspace_candidate" "${social_candidate:-}"; then
    echo "Skipping checkpoint run $run_id: structural memory validation failed."
    rm -rf "$run_dir"
    continue
  fi

  history_candidate="$run_dir/validated-checkpoint-history.jsonl"
  validator_args=(
    --workspace "$workspace_candidate"
    --summary "$summary_candidate"
    --history-output "$history_candidate"
  )
  if [[ -s "${social_candidate:-}" ]]; then
    validator_args+=(--social "$social_candidate")
  fi
  if [[ -e "$error_candidate" ]]; then
    validator_args+=(--error "$error_candidate")
  fi

  if ! validation_json="$(python3 checkpoint_validation.py "${validator_args[@]}")"; then
    echo "Skipping checkpoint run $run_id: completed-session validation failed."
    rm -rf "$run_dir"
    continue
  fi

  social_ok="$(python3 -c 'import json,sys; print("true" if json.load(sys.stdin).get("social_state_restorable") else "false")' <<< "$validation_json")"
  message_count="$(python3 -c 'import json,sys; print(int(json.load(sys.stdin).get("message_count", 0)))' <<< "$validation_json")"

  checkpoint_run="$run_id"
  checkpoint_conclusion="$run_conclusion"
  candidate="$workspace_candidate"
  checkpoint_summary="$summary_candidate"
  checkpoint_history="$history_candidate"
  checkpoint_message_count="$message_count"
  if [[ "$social_ok" == "true" ]]; then
    social_state="${social_candidate:-}"
  else
    social_state=""
  fi
  break
done

if [[ -z "$checkpoint_run" ]]; then
  echo "No successful, completed, semantically clean v2 checkpoint exists. Starting from clean cognition and social state."
  reset_clean "no_valid_successful_checkpoint_v2"
  exit 0
fi

new_workspaces="$HERE/.workspaces.restore.$$"
rm -rf "$new_workspaces"
cp -a "$candidate" "$new_workspaces"
rm -rf "$WORKSPACES"
mv "$new_workspaces" "$WORKSPACES"

mkdir -p "$REPLAY_DIR"
rm -f "$REPLAY_DIR/community_session.json" "$REPLAY_DIR/community_session_error.json"
cp "$checkpoint_summary" "$REPLAY_DIR/checkpoint_session.json.tmp"
mv "$REPLAY_DIR/checkpoint_session.json.tmp" "$REPLAY_DIR/checkpoint_session.json"
cp "$checkpoint_history" "$REPLAY_DIR/community_session.jsonl.tmp"
mv "$REPLAY_DIR/community_session.jsonl.tmp" "$REPLAY_DIR/community_session.jsonl"

social_restored=false
if [[ -n "$social_state" && -s "$social_state" ]]; then
  cp "$social_state" "$REPLAY_DIR/social_state.json.tmp"
  mv "$REPLAY_DIR/social_state.json.tmp" "$REPLAY_DIR/social_state.json"
  social_restored=true
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
  "validated_message_count": $checkpoint_message_count,
  "history_scoped_to_checkpoint": true,
  "social_state_restored": $social_restored
}
JSON
mv "$REPLAY_DIR/checkpoint_restore.json.tmp" "$REPLAY_DIR/checkpoint_restore.json"

echo "Restored Emily + Olivia workspaces from successful validated v2 checkpoint run $checkpoint_run."
echo "Checkpoint dialogue history scoped to that exact completed session: $checkpoint_message_count messages"
echo "Persistent social state restored: $social_restored"
