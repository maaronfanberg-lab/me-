#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$HERE/vendor"
AS_VENV="$HERE/.venv-agentsociety"
STANFORD_VENV="$HERE/.venv-stanford"
STANFORD_COMMIT="96854071ef4c2d79c93144c973c7820722d52bab"
PAPER_REPO="https://github.com/joonspk-research/generative_agents.git"
PAPER_COMMIT="fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4"
PAPER_DIR="$VENDOR/stanford-generative-agents-paper"
BITNET_REPO="https://github.com/raphaelbgr/BitNet.git"
BITNET_COMMIT="baecdf7d1e4d404d30f80ae5b26f486ca833ae03"
BITNET_DIR="$VENDOR/BitNet"
MODEL_DIR="$HERE/models/Falcon3-1B-Instruct-1.58bit"
MODEL_FILE="$MODEL_DIR/ggml-model-i2_s.gguf"
BITNET_SOURCE_REPO="tiiuae/Falcon3-1B-Instruct-1.58bit-GGUF"
BITNET_SOURCE_REVISION="4ec8c66"
READY_MARKER="$HERE/.bootstrap-ready-v11"
PORTABLE_BUILD_SIGNATURE="$BITNET_DIR/.community-portable-build-v14"

restore_real_cli() {
  if [[ -e "$BITNET_DIR/build/bin/llama-cli.real" ]]; then
    rm -f "$BITNET_DIR/build/bin/llama-cli"
    mv "$BITNET_DIR/build/bin/llama-cli.real" "$BITNET_DIR/build/bin/llama-cli"
  fi
}

runtime_ready() {
  [[ -f "$READY_MARKER" ]] || return 1
  [[ -f "$PORTABLE_BUILD_SIGNATURE" ]] || return 1
  [[ -x "$AS_VENV/bin/python" ]] || return 1
  [[ -x "$STANFORD_VENV/bin/python" ]] || return 1
  [[ -x "$BITNET_DIR/build/bin/llama-cli" ]] || return 1
  [[ -x "$BITNET_DIR/build/bin/llama-server" ]] || return 1
  [[ -s "$MODEL_FILE" ]] || return 1
  [[ "$(git -C "$VENDOR/stanford-genagents" rev-parse HEAD 2>/dev/null || true)" == "$STANFORD_COMMIT" ]] || return 1
  [[ "$(git -C "$PAPER_DIR" rev-parse HEAD 2>/dev/null || true)" == "$PAPER_COMMIT" ]] || return 1
  [[ "$(git -C "$BITNET_DIR" rev-parse HEAD 2>/dev/null || true)" == "$BITNET_COMMIT" ]] || return 1
}

restore_real_cli
if runtime_ready; then
  python3 "$HERE/patch_stanford_local.py"
  echo "Reusing cached portable Community runtime and pinned Stanford sources."
  exit 0
fi

rm -f \
  "$HERE/.bootstrap-ready-v7" \
  "$HERE/.bootstrap-ready-v8" \
  "$HERE/.bootstrap-ready-v9" \
  "$HERE/.bootstrap-ready-v10" \
  "$READY_MARKER"
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

# Keep the original paper implementation beside the later Stanford HCI package.
# We do not install its old web/game dependency stack; adapters can reuse the
# pinned Apache-2.0 source/templates while the modern genagents runtime handles
# memory, retrieval, reflection, and utterance generation.
if [[ ! -d "$PAPER_DIR/.git" ]]; then
  git clone "$PAPER_REPO" "$PAPER_DIR"
fi
if [[ "$(git -C "$PAPER_DIR" rev-parse HEAD 2>/dev/null || true)" != "$PAPER_COMMIT" ]]; then
  git -C "$PAPER_DIR" fetch --depth 1 origin "$PAPER_COMMIT"
  git -C "$PAPER_DIR" checkout --detach "$PAPER_COMMIT"
fi
[[ "$(git -C "$PAPER_DIR" rev-parse HEAD)" == "$PAPER_COMMIT" ]] || {
  echo "Original Stanford Generative Agents source is not at pinned commit $PAPER_COMMIT" >&2
  exit 1
}

if [[ ! -x "$STANFORD_VENV/bin/python" ]]; then
  python3 -m venv "$STANFORD_VENV"
fi
"$STANFORD_VENV/bin/python" -m pip install --disable-pip-version-check --upgrade pip
"$STANFORD_VENV/bin/python" -m pip install --disable-pip-version-check -r "$VENDOR/stanford-genagents/requirements.txt"

if [[ ! -d "$BITNET_DIR/.git" ]]; then
  git clone --recursive "$BITNET_REPO" "$BITNET_DIR"
else
  git -C "$BITNET_DIR" remote set-url origin "$BITNET_REPO"
  git -C "$BITNET_DIR" reset --hard
fi
if [[ "$(git -C "$BITNET_DIR" rev-parse HEAD 2>/dev/null || true)" != "$BITNET_COMMIT" ]]; then
  git -C "$BITNET_DIR" fetch --depth 1 origin "$BITNET_COMMIT"
  git -C "$BITNET_DIR" checkout --detach "$BITNET_COMMIT"
fi
git -C "$BITNET_DIR" submodule update --init --recursive

"$STANFORD_VENV/bin/python" -m pip install --disable-pip-version-check -r "$BITNET_DIR/requirements.txt"

COMPILER_BIN="$HERE/.bitnet-compiler-bin"
rm -rf "$COMPILER_BIN"
mkdir -p "$COMPILER_BIN"
if command -v clang-18 >/dev/null 2>&1 && command -v clang++-18 >/dev/null 2>&1; then
  ln -s "$(command -v clang-18)" "$COMPILER_BIN/clang"
  ln -s "$(command -v clang++-18)" "$COMPILER_BIN/clang++"
elif command -v clang-19 >/dev/null 2>&1 && command -v clang++-19 >/dev/null 2>&1; then
  ln -s "$(command -v clang-19)" "$COMPILER_BIN/clang"
  ln -s "$(command -v clang++-19)" "$COMPILER_BIN/clang++"
elif command -v clang >/dev/null 2>&1 && command -v clang++ >/dev/null 2>&1; then
  ln -s "$(command -v clang)" "$COMPILER_BIN/clang"
  ln -s "$(command -v clang++)" "$COMPILER_BIN/clang++"
else
  echo "No usable Clang compiler found" >&2
  exit 1
fi
export PATH="$COMPILER_BIN:$PATH"
echo "BitNet compiler: $(clang --version | head -n 1)"

BITNET_MAD="$BITNET_DIR/src/ggml-bitnet-mad.cpp"
if [[ -f "$BITNET_MAD" ]]; then
  "$STANFORD_VENV/bin/python" - "$BITNET_MAD" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = "int8_t * y_col = y + col * by;"
new = "const int8_t * y_col = y + col * by;"
if old in text:
    text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")
    print("Applied documented BitNet const-correctness patch.")
elif new in text:
    print("BitNet const-correctness patch already present.")
else:
    print("BitNet const-correctness target not present; continuing.")
PY
fi

BITNET_SETUP="$BITNET_DIR/setup_env.py"
"$STANFORD_VENV/bin/python" - "$BITNET_SETUP" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
if '"-DGGML_NATIVE=OFF"' not in text:
    needle = '"-DCMAKE_C_COMPILER=clang", "-DCMAKE_CXX_COMPILER=clang++"]'
    replacement = '"-DCMAKE_C_COMPILER=clang", "-DCMAKE_CXX_COMPILER=clang++", "-DGGML_NATIVE=OFF"]'
    if needle not in text:
        raise SystemExit("Could not locate pinned BitNet CMake argument list for portable-build patch")
    text = text.replace(needle, replacement, 1)
    path.write_text(text, encoding="utf-8")

check = path.read_text(encoding="utf-8")
if '"-DGGML_NATIVE=OFF"' not in check:
    raise SystemExit("Portable BitNet build patch did not persist")
print("BitNet setup patched for a portable GitHub Actions build.")
PY

if [[ ! -s "$MODEL_FILE" ]]; then
  echo "Downloading pinned official Falcon3 1.58-bit GGUF..."
  "$STANFORD_VENV/bin/huggingface-cli" download \
    "$BITNET_SOURCE_REPO" \
    "ggml-model-i2_s.gguf" \
    --revision "$BITNET_SOURCE_REVISION" \
    --local-dir "$MODEL_DIR"
fi

[[ -s "$MODEL_FILE" ]] || {
  echo "Pinned Falcon3 GGUF download did not produce $MODEL_FILE" >&2
  exit 1
}

rm -f "$PORTABLE_BUILD_SIGNATURE"
rm -rf "$BITNET_DIR/build"

echo "Building portable BitNet runtime for pinned Falcon3 GGUF..."
pushd "$BITNET_DIR" >/dev/null
if ! "$STANFORD_VENV/bin/python" setup_env.py -md "$MODEL_DIR" -q i2_s; then
  echo "BitNet setup failed; diagnostic logs follow:" >&2
  for log_file in logs/generate_build_files.log logs/compile.log logs/convert_to_f32_gguf.log logs/quantize_to_i2s.log; do
    if [[ -s "$log_file" ]]; then
      echo "---------------- $log_file ----------------" >&2
      tail -n 300 "$log_file" >&2 || true
    fi
  done
  echo "------------------------------------------------" >&2
  popd >/dev/null
  exit 1
fi
popd >/dev/null

restore_real_cli
[[ -x "$BITNET_DIR/build/bin/llama-cli" ]] || { echo "Missing BitNet llama-cli after build" >&2; exit 1; }
[[ -x "$BITNET_DIR/build/bin/llama-server" ]] || { echo "Missing BitNet llama-server after build" >&2; exit 1; }
[[ -s "$MODEL_FILE" ]] || { echo "Missing Falcon BitNet model after setup" >&2; exit 1; }

touch "$PORTABLE_BUILD_SIGNATURE"
python3 "$HERE/patch_stanford_local.py"
touch "$READY_MARKER"

printf 'AgentSociety2: 2.8.4 -> %s\n' "$AS_VENV"
printf 'Stanford genagents: %s -> %s\n' "$STANFORD_COMMIT" "$STANFORD_VENV"
printf 'Stanford paper source: %s -> %s\n' "$PAPER_COMMIT" "$PAPER_DIR"
printf 'BitNet: %s -> %s\n' "$BITNET_COMMIT" "$BITNET_DIR"
printf 'Falcon BitNet model: %s @ %s -> %s\n' "$BITNET_SOURCE_REPO" "$BITNET_SOURCE_REVISION" "$MODEL_FILE"
printf 'Portable build signature: %s\n' "$PORTABLE_BUILD_SIGNATURE"
printf 'Bootstrap marker: %s\n' "$READY_MARKER"
