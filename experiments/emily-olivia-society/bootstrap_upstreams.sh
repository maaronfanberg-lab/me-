#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$HERE/vendor"
AS_VENV="$HERE/.venv-agentsociety"
STANFORD_VENV="$HERE/.venv-stanford"
STANFORD_COMMIT="96854071ef4c2d79c93144c973c7820722d52bab"
BITNET_REPO="https://github.com/raphaelbgr/BitNet.git"
BITNET_COMMIT="baecdf7d1e4d404d30f80ae5b26f486ca833ae03"
BITNET_DIR="$VENDOR/BitNet"
MODEL_DIR="$HERE/models/BitNet-b1.58-2B-4T"
MODEL_FILE="$MODEL_DIR/ggml-model-i2_s.gguf"
BITNET_SOURCE_REPO="microsoft/BitNet-b1.58-2B-4T"
READY_MARKER="$HERE/.bootstrap-ready-v9"

restore_real_cli() {
  if [[ -e "$BITNET_DIR/build/bin/llama-cli.real" ]]; then
    rm -f "$BITNET_DIR/build/bin/llama-cli"
    mv "$BITNET_DIR/build/bin/llama-cli.real" "$BITNET_DIR/build/bin/llama-cli"
  fi
}

runtime_ready() {
  [[ -f "$READY_MARKER" ]] || return 1
  [[ -x "$AS_VENV/bin/python" ]] || return 1
  [[ -x "$STANFORD_VENV/bin/python" ]] || return 1
  [[ -x "$BITNET_DIR/build/bin/llama-cli" ]] || return 1
  [[ -x "$BITNET_DIR/build/bin/llama-server" ]] || return 1
  [[ -s "$MODEL_FILE" ]] || return 1
  [[ "$(git -C "$VENDOR/stanford-genagents" rev-parse HEAD 2>/dev/null || true)" == "$STANFORD_COMMIT" ]] || return 1
  [[ "$(git -C "$BITNET_DIR" rev-parse HEAD 2>/dev/null || true)" == "$BITNET_COMMIT" ]] || return 1
}

restore_real_cli
if runtime_ready; then
  python3 "$HERE/patch_stanford_local.py"
  echo "Reusing cached Community runtime and BitNet build."
  exit 0
fi

rm -f "$HERE/.bootstrap-ready-v7" "$HERE/.bootstrap-ready-v8" "$READY_MARKER"
mkdir -p "$VENDOR" "$MODEL_DIR"

if [[ ! -x "$AS_VENV/bin/python" ]]; then
  python3 -m venv "$AS_VENV"
fi
"$AS_VENV/bin/python" -m pip install --disable-pip-version-check --upgrade pip
"$AS_VENV/bin/python" -m pip install --disable-pip-version-check "agentsociety2==2.8.4" "mcp>=1.13.1,<2"

if [[ ! -d "$VENDOR/stanford-genagents/.git" ]]; then
  git clone https://github.com/StanfordHCI/genagents.git "$VENDOR/stanford-genagents"
fi
if [[ "$(git -C "$VENDOR/stanford-genagents" rev-parse HEAD 2>/dev/null || true)" != "$STANFORD_COMMIT" ]]; then
  git -C "$VENDOR/stanford-genagents" fetch --depth 1 origin "$STANFORD_COMMIT"
  git -C "$VENDOR/stanford-genagents" checkout --detach "$STANFORD_COMMIT"
fi

if [[ ! -x "$STANFORD_VENV/bin/python" ]]; then
  python3 -m venv "$STANFORD_VENV"
fi
"$STANFORD_VENV/bin/python" -m pip install --disable-pip-version-check --upgrade pip
"$STANFORD_VENV/bin/python" -m pip install --disable-pip-version-check -r "$VENDOR/stanford-genagents/requirements.txt"

if [[ ! -d "$BITNET_DIR/.git" ]]; then
  git clone --recursive "$BITNET_REPO" "$BITNET_DIR"
else
  git -C "$BITNET_DIR" remote set-url origin "$BITNET_REPO"
fi
if [[ "$(git -C "$BITNET_DIR" rev-parse HEAD 2>/dev/null || true)" != "$BITNET_COMMIT" ]]; then
  git -C "$BITNET_DIR" fetch --depth 1 origin "$BITNET_COMMIT"
  git -C "$BITNET_DIR" checkout --detach "$BITNET_COMMIT"
fi
git -C "$BITNET_DIR" submodule update --init --recursive

"$STANFORD_VENV/bin/python" -m pip install --disable-pip-version-check -r "$BITNET_DIR/requirements.txt"

# Microsoft's prebuilt GGUF is missing tokenizer.ggml.pre metadata and produces
# repeated/garbled text with bitnet.cpp. Use the upstream tokenizer fix and
# regenerate I2_S from the original model weights once, then cache the result.
if [[ ! -f "$MODEL_DIR/config.json" || ! -f "$MODEL_DIR/tokenizer.json" ]]; then
  echo "Downloading original BitNet weights and tokenizer metadata..."
  "$STANFORD_VENV/bin/huggingface-cli" download \
    "$BITNET_SOURCE_REPO" \
    --local-dir "$MODEL_DIR"
fi

# Never keep the known-bad published GGUF when entering the v9 rebuild path.
rm -f "$MODEL_FILE"
rm -rf "$BITNET_DIR/build"

echo "Building BitNet runtime and regenerating tokenizer-correct I2_S GGUF..."
pushd "$BITNET_DIR" >/dev/null
"$STANFORD_VENV/bin/python" setup_env.py -md "$MODEL_DIR" -q i2_s
popd >/dev/null

restore_real_cli
[[ -x "$BITNET_DIR/build/bin/llama-cli" ]] || { echo "Missing BitNet llama-cli after build" >&2; exit 1; }
[[ -x "$BITNET_DIR/build/bin/llama-server" ]] || { echo "Missing BitNet llama-server after build" >&2; exit 1; }
[[ -s "$MODEL_FILE" ]] || { echo "Missing BitNet model after setup" >&2; exit 1; }

python3 "$HERE/patch_stanford_local.py"
touch "$READY_MARKER"

printf 'AgentSociety2: 2.8.4 -> %s\n' "$AS_VENV"
printf 'Stanford genagents: %s -> %s\n' "$STANFORD_COMMIT" "$STANFORD_VENV"
printf 'BitNet: %s -> %s\n' "$BITNET_COMMIT" "$BITNET_DIR"
printf 'BitNet model: %s\n' "$MODEL_FILE"
printf 'Bootstrap marker: %s\n' "$READY_MARKER"
