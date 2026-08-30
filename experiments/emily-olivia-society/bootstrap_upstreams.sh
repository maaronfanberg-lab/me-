#!/usr/bin/env bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENDOR="$HERE/vendor"
AS_VENV="$HERE/.venv-agentsociety"
STANFORD_VENV="$HERE/.venv-stanford"
STANFORD_COMMIT="96854071ef4c2d79c93144c973c7820722d52bab"

python3 -m venv "$AS_VENV"
"$AS_VENV/bin/python" -m pip install --upgrade pip
"$AS_VENV/bin/python" -m pip install "agentsociety2==2.8.4" "mcp>=1.13.1,<2"

mkdir -p "$VENDOR"
if [[ ! -d "$VENDOR/stanford-genagents/.git" ]]; then
  git clone https://github.com/StanfordHCI/genagents.git "$VENDOR/stanford-genagents"
fi

git -C "$VENDOR/stanford-genagents" fetch --all --tags --prune
git -C "$VENDOR/stanford-genagents" checkout --detach "$STANFORD_COMMIT"

# Compatibility patch for the pinned Stanford code. The upstream importance
# parser assumes every model response contains a JSON object and crashes on
# otherwise-valid non-JSON output. Keep the pinned source, but make its existing
# fail-safe path return one neutral importance score per record.
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

# Stanford's pinned memory stream otherwise calls the OpenAI embeddings API
# directly. For this bounded experiment, use a deterministic local hashed-token
# embedding instead. This preserves stable cosine-similarity retrieval while
# removing an unnecessary network/API-key failure point.
STANFORD_GPT="$VENDOR/stanford-genagents/simulation_engine/gpt_structure.py"
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

# The pinned utterance parser also assumes every model response is a JSON
# object containing an `utterance` key. API errors and ordinary text responses
# violate that assumption, so normalize them to a harmless bounded reply rather
# than crashing the entire social cycle.
STANFORD_INTERACTION="$VENDOR/stanford-genagents/genagents/modules/interaction.py"
python3 - "$STANFORD_INTERACTION" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = '''  def _func_clean_up(gpt_response, prompt=""): \n    utterance = extract_first_json_dict(gpt_response)["utterance"]\n    return utterance\n\n  def _get_fail_safe():\n    return None\n'''
new = '''  def _func_clean_up(gpt_response, prompt=""): \n    parsed = extract_first_json_dict(gpt_response)\n    if isinstance(parsed, dict):\n      utterance = parsed.get("utterance")\n      if isinstance(utterance, str) and utterance.strip():\n        return utterance.strip()\n    if isinstance(gpt_response, str):\n      candidate = gpt_response.strip()\n      if candidate and not candidate.startswith("GENERATION ERROR:"):\n        return candidate[:1000]\n    return "I am here and listening."\n\n  def _get_fail_safe():\n    return "I am here and listening."\n'''
if old not in text:
    raise SystemExit("Pinned Stanford utterance parser changed; compatibility patch no longer applies cleanly.")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
PY

python3 -m venv "$STANFORD_VENV"
"$STANFORD_VENV/bin/python" -m pip install --upgrade pip
"$STANFORD_VENV/bin/python" -m pip install -r "$VENDOR/stanford-genagents/requirements.txt"

printf 'AgentSociety2: 2.8.4 -> %s\n' "$AS_VENV"
printf 'Stanford genagents: %s -> %s\n' "$STANFORD_COMMIT" "$STANFORD_VENV"
printf 'Initialize cognition with: %s init_cognition.py\n' "$STANFORD_VENV/bin/python"
printf 'Initialize society with: %s run.py\n' "$AS_VENV/bin/python"
