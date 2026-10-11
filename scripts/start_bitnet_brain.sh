#!/usr/bin/env bash
set -euo pipefail

# Isolated BitNet brain launcher for The Room.
# This does not modify the live Room. Point ROOM_MODEL_URL at this server only
# when you explicitly want to test BitNet.

BITNET_HOME="${BITNET_HOME:-$HOME/BitNet}"
BITNET_MODEL="${BITNET_MODEL:-}"
BITNET_HOST="${BITNET_HOST:-127.0.0.1}"
BITNET_PORT="${BITNET_PORT:-8081}"
BITNET_THREADS="${BITNET_THREADS:-4}"
BITNET_CTX_SIZE="${BITNET_CTX_SIZE:-2048}"
BITNET_N_PREDICT="${BITNET_N_PREDICT:-256}"
BITNET_TEMPERATURE="${BITNET_TEMPERATURE:-0.7}"

if [[ ! -d "$BITNET_HOME" ]]; then
  echo "BitNet checkout not found at: $BITNET_HOME" >&2
  echo "Clone it with: git clone --recursive https://github.com/microsoft/BitNet.git \"$BITNET_HOME\"" >&2
  exit 2
fi

if [[ -z "$BITNET_MODEL" ]]; then
  echo "BITNET_MODEL must point to a prepared BitNet GGUF model." >&2
  exit 2
fi

if [[ ! -f "$BITNET_MODEL" ]]; then
  echo "BitNet model not found: $BITNET_MODEL" >&2
  exit 2
fi

cd "$BITNET_HOME"

SERVER="$BITNET_HOME/build/bin/llama-server"
if [[ ! -x "$SERVER" ]]; then
  echo "BitNet llama-server not built at: $SERVER" >&2
  echo "Run Microsoft's setup_env.py for your model first." >&2
  exit 3
fi

echo "Starting isolated BitNet brain on http://${BITNET_HOST}:${BITNET_PORT}"
echo "Room test setting: export ROOM_MODEL_URL=http://${BITNET_HOST}:${BITNET_PORT}"

exec "$SERVER" \
  -m "$BITNET_MODEL" \
  -c "$BITNET_CTX_SIZE" \
  -t "$BITNET_THREADS" \
  -n "$BITNET_N_PREDICT" \
  -ngl 0 \
  --temp "$BITNET_TEMPERATURE" \
  --host "$BITNET_HOST" \
  --port "$BITNET_PORT" \
  -cb
