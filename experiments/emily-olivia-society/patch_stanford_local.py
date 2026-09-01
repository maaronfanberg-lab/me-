#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
STANFORD = HERE / "vendor" / "stanford-genagents"


def replace_once(path: Path, old: str, new: str, marker: str) -> None:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    if old not in text:
        raise SystemExit(f"Pinned Stanford source changed; patch target not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_one_of(path: Path, olds: tuple[str, ...], new: str, marker: str) -> None:
    """Apply an idempotent upgrade from pristine or previously patched cached source."""
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    for old in olds:
        if old in text:
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
            return
    raise SystemExit(f"Pinned Stanford source changed; no supported patch target found in {path}")


def patch_gpt() -> None:
    path = STANFORD / "simulation_engine" / "gpt_structure.py"
    text = path.read_text(encoding="utf-8")
    marker = "COMMUNITY_BITNET_TEMPLATE_V6"
    if marker in text:
        return

    # Stanford's generated prompt is a meta-instruction asking the model to
    # produce JSON character speech, not a conversational message from either
    # community member. Apply Falcon3's native chat template with that complete
    # Stanford instruction in the system role, then generate through /completion.
    # llama.cpp's /apply-template supplies the model-native assistant generation
    # marker without adding a generic assistant persona or changing Stanford text.
    pattern = re.compile(r"def gpt_request\(.*?(?=\ndef get_text_embedding\()", re.S)
    match = pattern.search(text)
    if not match:
        raise SystemExit("Pinned Stanford generation layout changed")
    replacement = '''def gpt_request(prompt: str,\n                model: str = "community-bitnet",\n                max_tokens: int = 1500) -> str:\n  """COMMUNITY_BITNET_TEMPLATE_V6; COMMUNITY_BITNET_HTTP_V4 compatibility marker."""\n  try:\n    import json\n    import os\n    import urllib.request\n    port = int(os.environ.get("COMMUNITY_BITNET_PORT", "8080"))\n    template_payload = json.dumps({\n      "messages": [\n        {"role": "system", "content": prompt},\n      ],\n    }).encode("utf-8")\n    template_req = urllib.request.Request(f"http://127.0.0.1:{port}/apply-template", data=template_payload, headers={"Content-Type": "application/json"}, method="POST")\n    with urllib.request.urlopen(template_req, timeout=int(os.environ.get("COMMUNITY_GENERATION_TIMEOUT", "900"))) as response:\n      template_data = json.loads(response.read().decode("utf-8"))\n    formatted_prompt = template_data.get("prompt") if isinstance(template_data, dict) else None\n    if not isinstance(formatted_prompt, str) or not formatted_prompt.strip():\n      raise RuntimeError(f"BitNet apply-template endpoint returned no usable prompt: {template_data!r}")\n    payload = json.dumps({\n      "prompt": formatted_prompt,\n      "n_predict": min(int(max_tokens), max(128, int(os.environ.get("COMMUNITY_MAX_TOKENS", "96")))),\n      "temperature": 0.7,\n      "top_p": 0.9,\n      "stream": False,\n      "cache_prompt": False,\n    }).encode("utf-8")\n    req = urllib.request.Request(f"http://127.0.0.1:{port}/completion", data=payload, headers={"Content-Type": "application/json"}, method="POST")\n    with urllib.request.urlopen(req, timeout=int(os.environ.get("COMMUNITY_GENERATION_TIMEOUT", "900"))) as response:\n      data = json.loads(response.read().decode("utf-8"))\n    content = data.get("content") if isinstance(data, dict) else None\n    if not isinstance(content, str) or not content.strip():\n      raise RuntimeError(f"BitNet completion endpoint returned no usable content: {data!r}")\n    return content.strip()\n  except Exception as e:\n    return f"GENERATION ERROR: {str(e)}"\n\n\ndef chat_safe_generate(prompt_input: Union[str, List[str]],\n                       prompt_lib_file: str,\n                       gpt_version: str = "community-bitnet",\n                       repeat: int = 1,\n                       fail_safe = "error",\n                       func_clean_up: callable = None,\n                       verbose: bool = False,\n                       max_tokens: int = 1500,\n                       file_attachment: str = None,\n                       file_type: str = None) -> tuple:\n  """Generate with local BitNet while preserving Stanford's helper contract."""\n  if file_attachment or file_type:\n    raise RuntimeError("Community local BitNet path does not support attachments.")\n  prompt = generate_prompt(prompt_input, prompt_lib_file)\n  response = fail_safe\n  attempts = max(1, int(repeat))\n  for i in range(attempts):\n    response = gpt_request(prompt, model=gpt_version, max_tokens=max_tokens)\n    if not (isinstance(response, str) and response.startswith("GENERATION ERROR:")):\n      break\n    if i + 1 < attempts:\n      time.sleep(2**i)\n  if isinstance(response, str) and response.startswith("GENERATION ERROR:"):\n    raise RuntimeError(response)\n  if func_clean_up:\n    response = func_clean_up(response, prompt=prompt)\n  if verbose or DEBUG:\n    print_run_prompts(prompt_input, prompt, response)\n  return response, prompt, prompt_input, fail_safe\n\n'''
    text = text[:match.start()] + replacement + text[match.end():]

    emb_pattern = re.compile(r"def get_text_embedding\(.*?(?=\n(?:def |class )|\Z)", re.S)
    emb_match = emb_pattern.search(text)
    if not emb_match:
        raise SystemExit("Pinned Stanford embedding layout changed")
    emb_replacement = '''def get_text_embedding(text: str,\n                       model: str = "local-hash") -> List[float]:\n  """Generate a deterministic local embedding without any external API."""\n  if not isinstance(text, str) or not text.strip():\n    raise ValueError("Input text must be a non-empty string.")\n  import hashlib\n  import math\n  import re\n  dims = 256\n  vector = [0.0] * dims\n  for token in re.findall(r"\\w+", text.lower()):\n    digest = hashlib.sha256(token.encode("utf-8")).digest()\n    index = int.from_bytes(digest[:4], "big") % dims\n    vector[index] += 1.0 if digest[4] & 1 else -1.0\n  norm = math.sqrt(sum(value * value for value in vector)) or 1.0\n  return [value / norm for value in vector]\n'''
    text = text[:emb_match.start()] + emb_replacement + text[emb_match.end():]
    path.write_text(text, encoding="utf-8")


def patch_memory() -> None:
    path = STANFORD / "genagents" / "modules" / "memory_stream.py"
    pristine = '''  def _func_clean_up(gpt_response, prompt=""): \n    gpt_response = extract_first_json_dict(gpt_response)\n    return list(gpt_response.values())\n\n  def _get_fail_safe():\n    return 25\n'''
    previous_patch = '''  def _func_clean_up(gpt_response, prompt=""): \n    gpt_response = extract_first_json_dict(gpt_response)\n    if not isinstance(gpt_response, dict):\n      return [25 for _ in records]\n    values = list(gpt_response.values())\n    if len(values) != len(records):\n      return [25 for _ in records]\n    return values\n\n  def _get_fail_safe():\n    return [25 for _ in records]\n'''
    numeric_patch = '''  def _func_clean_up(gpt_response, prompt=""): \n    gpt_response = extract_first_json_dict(gpt_response)\n    if not isinstance(gpt_response, dict):\n      return [25 for _ in records]\n    values = list(gpt_response.values())\n    if len(values) != len(records):\n      return [25 for _ in records]\n    cleaned = []\n    for value in values:\n      try:\n        score = float(value)\n      except (TypeError, ValueError):\n        score = 25.0\n      cleaned.append(max(0.0, min(100.0, score)))\n    return cleaned\n\n  def _get_fail_safe():\n    return [25 for _ in records]\n'''
    replace_one_of(
        path,
        (pristine, previous_patch),
        numeric_patch,
        "cleaned.append(max(0.0, min(100.0, score)))",
    )
    replace_once(
        path,
        '''  def _func_clean_up(gpt_response, prompt=""): \n    return extract_first_json_dict(gpt_response)["reflection"]\n\n  def _get_fail_safe():\n    return []\n''',
        '''  def _func_clean_up(gpt_response, prompt=""): \n    if isinstance(gpt_response, str) and gpt_response.strip().startswith("GENERATION ERROR:"):\n      raise RuntimeError(gpt_response.strip())\n    parsed = extract_first_json_dict(gpt_response)\n    if isinstance(parsed, dict):\n      reflection = parsed.get("reflection")\n      if isinstance(reflection, list):\n        return reflection[:reflection_count]\n      if isinstance(reflection, str) and reflection.strip():\n        return [reflection.strip()]\n    if isinstance(gpt_response, str) and gpt_response.strip():\n      return [gpt_response.strip()[:1000]]\n    return []\n\n  def _get_fail_safe():\n    return []\n''',
        "return [gpt_response.strip()[:1000]]",
    )


def patch_interaction() -> None:
    path = STANFORD / "genagents" / "modules" / "interaction.py"
    replace_once(
        path,
        '''  def _func_clean_up(gpt_response, prompt=""): \n    utterance = extract_first_json_dict(gpt_response)["utterance"]\n    return utterance\n\n  def _get_fail_safe():\n    return None\n''',
        '''  def _func_clean_up(gpt_response, prompt=""): \n    if isinstance(gpt_response, str) and gpt_response.strip().startswith("GENERATION ERROR:"):\n      raise RuntimeError(gpt_response.strip())\n    parsed = extract_first_json_dict(gpt_response)\n    if isinstance(parsed, dict):\n      utterance = parsed.get("utterance")\n      if isinstance(utterance, str) and utterance.strip():\n        return utterance.strip()\n    if isinstance(gpt_response, str) and gpt_response.strip():\n      return gpt_response.strip()[:1000]\n    raise RuntimeError("Model returned no usable utterance.")\n\n  def _get_fail_safe():\n    return None\n''',
        "Model returned no usable utterance.",
    )


def main() -> None:
    if not STANFORD.exists():
        raise SystemExit("Stanford runtime is not present")
    patch_gpt()
    patch_memory()
    patch_interaction()
    print("Stanford runtime patched for Falcon-native local BitNet generation.")


if __name__ == "__main__":
    main()
