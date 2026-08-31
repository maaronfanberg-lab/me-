#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$HERE/vendor"
AS_VENV="$HERE/.venv-agentsociety"
STANFORD_VENV="$HERE/.venv-stanford"
STANFORD_COMMIT="96854071ef4c2d79c93144c973c7820722d52bab"
READY_MARKER="$HERE/.bootstrap-ready-v4"
MODEL_DIR="$HERE/models"
MODEL_FILE="$MODEL_DIR/qwen2.5-0.5b-instruct-q4_k_m.gguf"
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf?download=true"

if [[ -f "$READY_MARKER" && -x "$AS_VENV/bin/python" && -x "$STANFORD_VENV/bin/python" && -d "$VENDOR/stanford-genagents/.git" && -s "$MODEL_FILE" ]]; then
  current_commit="$(git -C "$VENDOR/stanford-genagents" rev-parse HEAD 2>/dev/null || true)"
  if [[ "$current_commit" == "$STANFORD_COMMIT" ]]; then
    echo "Reusing cached Community runtime environments and local model."
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
new = '''_LOCAL_LLM = None\n\ndef _get_local_llm():\n  global _LOCAL_LLM\n  if _LOCAL_LLM is None:\n    import os\n    from pathlib import Path\n    from llama_cpp import Llama\n    default_model = Path(__file__).resolve().parents[3] / "models" / "qwen2.5-0.5b-instruct-q4_k_m.gguf"\n    model_path = Path(os.environ.get("COMMUNITY_LOCAL_MODEL", str(default_model)))\n    if not model_path.exists():\n      raise FileNotFoundError(f"Local Community model not found: {model_path}")\n    _LOCAL_LLM = Llama(\n      model_path=str(model_path),\n      n_ctx=4096,\n      n_threads=max(2, min(6, os.cpu_count() or 2)),\n      verbose=False,\n    )\n  return _LOCAL_LLM\n\ndef gpt_request(prompt: str, \n                model: str = "community-local", \n                max_tokens: int = 1500) -> str:\n  """Generate locally with Qwen through llama.cpp; no paid API is required."""\n  try:\n    llm = _get_local_llm()\n    response = llm.create_chat_completion(\n      messages=[{"role": "user", "content": prompt}],\n      max_tokens=min(max_tokens, 256),\n      temperature=0.7,\n    )\n    return response["choices"][0]["message"]["content"]\n  except Exception as e:\n    return f"GENERATION ERROR: {str(e)}"\n'''
if old not in text:
    raise SystemExit("Pinned Stanford GPT request helper changed; local-model patch no longer applies cleanly.")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY

python3 - "$STANFORD_GPT" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = '''def get_text_embedding(text: str, \n                       model: str = "text-embedding-3-small") -> List[float]:\n  """Generate an embedding for the given text using OpenAI's API."""\n  if not isinstance(text, str) or not text.strip():\n    raise ValueError("Input text must be a non-empty string.")\n\n  text = text.replace("\\n", " ").strip()\n  response = openai.embeddings.create(\n    input=[text], model=model).data[0].embedding\n  return response\n'''
new = '''def get_text_embedding(text: str, \n                       model: str = "text-embedding-3-small") -> List[float]:\n  """Generate a deterministic local embedding for bounded experiments."""\n  if not isinstance(text, str) or not text.strip():\n    raise ValueError("Input text must be a non-empty string.")\n\n  import hashlib\n  import math\n  import re\n\n  dims = 256\n  vector = [0.0] * dims\n  for token in re.findall(r"\\w+", text.lower()):\n    digest = hashlib.sha256(token.encode("utf-8")).digest()\n    index = int.from_bytes(digest[:4], "big") % dims\n    sign = 1.0 if digest[4] & 1 else -1.0\n    vector[index] += sign\n\n  norm = math.sqrt(sum(value * value for value in vector)) or 1.0\n  return [value / norm for value in vector]\n'''
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
"$STANFORD_VENV/bin/python" -m pip install \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu \
  "llama-cpp-python>=0.3.9,<0.4"

mkdir -p "$MODEL_DIR"
if [[ ! -s "$MODEL_FILE" ]]; then
  echo "Downloading free local Community model (Qwen2.5 0.5B, Q4_K_M)..."
  curl -L --fail --retry 3 --retry-delay 2 "$MODEL_URL" -o "$MODEL_FILE.part"
  mv "$MODEL_FILE.part" "$MODEL_FILE"
fi

# Sanity-check that the model can actually generate before marking the cache ready.
COMMUNITY_LOCAL_MODEL="$MODEL_FILE" "$STANFORD_VENV/bin/python" - <<'PY'
import os
from llama_cpp import Llama
llm = Llama(model_path=os.environ["COMMUNITY_LOCAL_MODEL"], n_ctx=1024, n_threads=2, verbose=False)
out = llm.create_chat_completion(
    messages=[{"role": "user", "content": "Reply with exactly: local-model-ok"}],
    max_tokens=16,
    temperature=0.0,
)
text = out["choices"][0]["message"]["content"].strip()
if not text:
    raise SystemExit("Local model produced an empty response.")
print("LOCAL_MODEL_PROBE:", text)
PY

touch "$READY_MARKER"
printf 'AgentSociety2: 2.8.4 -> %s\n' "$AS_VENV"
printf 'Stanford genagents: %s -> %s\n' "$STANFORD_COMMIT" "$STANFORD_VENV"
printf 'Local model: Qwen2.5-0.5B-Instruct Q4_K_M -> %s\n' "$MODEL_FILE"
printf 'Initialize cognition with: %s init_cognition.py\n' "$STANFORD_VENV/bin/python"
printf 'Initialize society with: %s run.py\n' "$AS_VENV/bin/python"
