#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$HERE/vendor"
AS_VENV="$HERE/.venv-agentsociety"
STANFORD_VENV="$HERE/.venv-stanford"
STANFORD_COMMIT="96854071ef4c2d79c93144c973c7820722d52bab"
BITNET_COMMIT="0b341e582afbf9e1011f24744b554c96a3477eb5"
BITNET_DIR="$VENDOR/BitNet"
MODEL_DIR="$HERE/models/BitNet-b1.58-2B-4T"
MODEL_FILE="$MODEL_DIR/ggml-model-i2_s.gguf"
READY_MARKER="$HERE/.bootstrap-ready-v5"

if [[ -f "$READY_MARKER" && -x "$AS_VENV/bin/python" && -x "$STANFORD_VENV/bin/python" && -x "$BITNET_DIR/build/bin/llama-cli" && -s "$MODEL_FILE" ]]; then
  stanford_current="$(git -C "$VENDOR/stanford-genagents" rev-parse HEAD 2>/dev/null || true)"
  bitnet_current="$(git -C "$BITNET_DIR" rev-parse HEAD 2>/dev/null || true)"
  if [[ "$stanford_current" == "$STANFORD_COMMIT" && "$bitnet_current" == "$BITNET_COMMIT" ]]; then
    echo "Reusing cached Community runtime and BitNet model."
    exit 0
  fi
fi

rm -f "$READY_MARKER"
python3 -m venv "$AS_VENV"
"$AS_VENV/bin/python" -m pip install --upgrade pip
"$AS_VENV/bin/python" -m pip install "agentsociety2==2.8.4" "mcp>=1.13.1,<2"

mkdir -p "$VENDOR"
if [[ ! -d "$VENDOR/stanford-genagents/.git" ]]; then
  git clone https://github.com/StanfordHCI/genagents.git "$VENDOR/stanford-genagents"
fi
git -C "$VENDOR/stanford-genagents" fetch --all --tags --prune
git -C "$VENDOR/stanford-genagents" checkout --detach "$STANFORD_COMMIT"

STANFORD_MEMORY="$VENDOR/stanford-genagents/genagents/modules/memory_stream.py"
python3 - "$STANFORD_MEMORY" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = '''  def _func_clean_up(gpt_response, prompt=""): \n    gpt_response = extract_first_json_dict(gpt_response)\n    return list(gpt_response.values())\n\n  def _get_fail_safe():\n    return 25\n'''
new = '''  def _func_clean_up(gpt_response, prompt=""): \n    gpt_response = extract_first_json_dict(gpt_response)\n    if not isinstance(gpt_response, dict):\n      return [25 for _ in records]\n    values = list(gpt_response.values())\n    if len(values) != len(records):\n      return [25 for _ in records]\n    return values\n\n  def _get_fail_safe():\n    return [25 for _ in records]\n'''
if old not in text:
    raise SystemExit("Pinned Stanford importance parser changed; compatibility patch no longer applies cleanly.")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY

python3 - "$STANFORD_MEMORY" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = '''  def _func_clean_up(gpt_response, prompt=""): \n    return extract_first_json_dict(gpt_response)["reflection"]\n\n  def _get_fail_safe():\n    return []\n'''
new = '''  def _func_clean_up(gpt_response, prompt=""): \n    if isinstance(gpt_response, str) and gpt_response.strip().startswith("GENERATION ERROR:"):\n      raise RuntimeError(gpt_response.strip())\n    parsed = extract_first_json_dict(gpt_response)\n    if isinstance(parsed, dict):\n      reflection = parsed.get("reflection")\n      if isinstance(reflection, list):\n        return reflection[:reflection_count]\n      if isinstance(reflection, str) and reflection.strip():\n        return [reflection.strip()]\n    if isinstance(gpt_response, str):\n      candidate = gpt_response.strip()\n      if candidate:\n        return [candidate[:1000]]\n    return []\n\n  def _get_fail_safe():\n    return []\n'''
if old not in text:
    raise SystemExit("Pinned Stanford reflection parser changed; compatibility patch no longer applies cleanly.")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY

STANFORD_GPT="$VENDOR/stanford-genagents/simulation_engine/gpt_structure.py"
python3 - "$STANFORD_GPT" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = '''def gpt_request(prompt: str, \n                model: str = "gpt-4o", \n                max_tokens: int = 1500) -> str:\n  """Make a request to OpenAI's GPT model."""\n  if model == "o1-preview": \n    try:\n      client = openai.OpenAI(api_key=OPENAI_API_KEY)\n      response = client.chat.completions.create(\n        model=model,\n        messages=[{"role": "user", "content": prompt}]\n      )\n      return response.choices[0].message.content\n    except Exception as e:\n      return f"GENERATION ERROR: {str(e)}"\n\n  try:\n    client = openai.OpenAI(api_key=OPENAI_API_KEY)\n    response = client.chat.completions.create(\n      model=model,\n      messages=[{"role": "user", "content": prompt}],\n      max_tokens=max_tokens,\n      temperature=0.7\n    )\n    return response.choices[0].message.content\n  except Exception as e:\n    return f"GENERATION ERROR: {str(e)}"\n'''
new = '''def gpt_request(prompt: str, \n                model: str = "community-bitnet", \n                max_tokens: int = 1500) -> str:\n  """Generate locally with Microsoft's BitNet b1.58; no paid API is required."""\n  try:\n    import os\n    import subprocess\n    from pathlib import Path\n    root = Path(os.environ["COMMUNITY_BITNET_ROOT"])\n    model_path = Path(os.environ["COMMUNITY_BITNET_MODEL"])\n    binary = root / "build" / "bin" / "llama-cli"\n    if not binary.exists():\n      raise FileNotFoundError(f"BitNet llama-cli not found: {binary}")\n    if not model_path.exists():\n      raise FileNotFoundError(f"BitNet model not found: {model_path}")\n    result = subprocess.run(\n      [str(binary), "-m", str(model_path), "-n", str(min(max_tokens, 256)),\n       "-t", str(max(2, min(6, os.cpu_count() or 2))), "-c", "4096",\n       "--temp", "0.7", "--no-display-prompt", "-p", prompt],\n      cwd=str(root), capture_output=True, text=True, timeout=180, check=True,\n    )\n    text = result.stdout.strip()\n    if not text:\n      raise RuntimeError("BitNet produced an empty response.")\n    return text\n  except Exception as e:\n    return f"GENERATION ERROR: {str(e)}"\n'''
if old not in text:
    raise SystemExit("Pinned Stanford GPT request helper changed; BitNet patch no longer applies cleanly.")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY

python3 - "$STANFORD_GPT" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = '''def get_text_embedding(text: str, \n                       model: str = "text-embedding-3-small") -> List[float]:\n  """Generate an embedding for the given text using OpenAI's API."""\n  if not isinstance(text, str) or not text.strip():\n    raise ValueError("Input text must be a non-empty string.")\n\n  text = text.replace("\\n", " ").strip()\n  response = openai.embeddings.create(\n    input=[text], model=model).data[0].embedding\n  return response\n'''
new = '''def get_text_embedding(text: str, \n                       model: str = "local-hash") -> List[float]:\n  """Generate a deterministic local embedding without an API call."""\n  if not isinstance(text, str) or not text.strip():\n    raise ValueError("Input text must be a non-empty string.")\n  import hashlib\n  import math\n  import re\n  dims = 256\n  vector = [0.0] * dims\n  for token in re.findall(r"\\w+", text.lower()):\n    digest = hashlib.sha256(token.encode("utf-8")).digest()\n    index = int.from_bytes(digest[:4], "big") % dims\n    vector[index] += 1.0 if digest[4] & 1 else -1.0\n  norm = math.sqrt(sum(value * value for value in vector)) or 1.0\n  return [value / norm for value in vector]\n'''
if old not in text:
    raise SystemExit("Pinned Stanford embedding helper changed; local embedding patch no longer applies cleanly.")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY

STANFORD_INTERACTION="$VENDOR/stanford-genagents/genagents/modules/interaction.py"
python3 - "$STANFORD_INTERACTION" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = '''  def _func_clean_up(gpt_response, prompt=""): \n    utterance = extract_first_json_dict(gpt_response)["utterance"]\n    return utterance\n\n  def _get_fail_safe():\n    return None\n'''
new = '''  def _func_clean_up(gpt_response, prompt=""): \n    if isinstance(gpt_response, str) and gpt_response.strip().startswith("GENERATION ERROR:"):\n      raise RuntimeError(gpt_response.strip())\n    parsed = extract_first_json_dict(gpt_response)\n    if isinstance(parsed, dict):\n      utterance = parsed.get("utterance")\n      if isinstance(utterance, str) and utterance.strip():\n        return utterance.strip()\n    if isinstance(gpt_response, str):\n      candidate = gpt_response.strip()\n      if candidate:\n        return candidate[:1000]\n    raise RuntimeError("Model returned no usable utterance.")\n\n  def _get_fail_safe():\n    return None\n'''
if old not in text:
    raise SystemExit("Pinned Stanford utterance parser changed; compatibility patch no longer applies cleanly.")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY

python3 -m venv "$STANFORD_VENV"
"$STANFORD_VENV/bin/python" -m pip install --upgrade pip
"$STANFORD_VENV/bin/python" -m pip install -r "$VENDOR/stanford-genagents/requirements.txt"

if [[ ! -d "$BITNET_DIR/.git" ]]; then
  git clone --recursive https://github.com/microsoft/BitNet.git "$BITNET_DIR"
fi
git -C "$BITNET_DIR" fetch --all --tags --prune
git -C "$BITNET_DIR" checkout --detach "$BITNET_COMMIT"
git -C "$BITNET_DIR" submodule update --init --recursive

"$STANFORD_VENV/bin/python" -m pip install -r "$BITNET_DIR/requirements.txt"
mkdir -p "$MODEL_DIR"
if [[ ! -s "$MODEL_FILE" ]]; then
  echo "Downloading Microsoft's free BitNet b1.58 2B model..."
  "$STANFORD_VENV/bin/huggingface-cli" download microsoft/BitNet-b1.58-2B-4T-gguf ggml-model-i2_s.gguf --local-dir "$MODEL_DIR"
fi

pushd "$BITNET_DIR" >/dev/null
"$STANFORD_VENV/bin/python" setup_env.py -md "$MODEL_DIR" -q i2_s
popd >/dev/null

COMMUNITY_BITNET_ROOT="$BITNET_DIR" COMMUNITY_BITNET_MODEL="$MODEL_FILE" "$STANFORD_VENV/bin/python" - <<'PY'
import os, subprocess
binary = os.path.join(os.environ["COMMUNITY_BITNET_ROOT"], "build", "bin", "llama-cli")
result = subprocess.run([
    binary, "-m", os.environ["COMMUNITY_BITNET_MODEL"], "-n", "24", "-t", "2", "-c", "1024",
    "--temp", "0", "--no-display-prompt", "-p", "Reply briefly: BitNet is working."
], cwd=os.environ["COMMUNITY_BITNET_ROOT"], capture_output=True, text=True, timeout=180, check=True)
text = result.stdout.strip()
if not text:
    raise SystemExit("BitNet local probe produced no text.")
print("BITNET_PROBE:", text[:300])
PY

touch "$READY_MARKER"
printf 'AgentSociety2: 2.8.4 -> %s\n' "$AS_VENV"
printf 'Stanford genagents: %s -> %s\n' "$STANFORD_COMMIT" "$STANFORD_VENV"
printf 'BitNet: %s -> %s\n' "$BITNET_COMMIT" "$BITNET_DIR"
printf 'BitNet model: %s\n' "$MODEL_FILE"
