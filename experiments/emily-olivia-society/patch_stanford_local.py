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
    'Apply an idempotent upgrade from pristine or previously patched cached source.'
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
    marker = "COMMUNITY_BITNET_CHAT_V7"
    if marker in text:
        return

    # The pinned BitNet llama-server exposes the documented OpenAI-compatible
    # chat-completions route, which applies Falcon's native chat template.
    # Stanford still owns prompt assembly; local generation simply routes the
    # completed prompt through the persistent BitNet server.
    pattern = re.compile(r"def gpt_request\(.*?(?=\ndef get_text_embedding\()", re.S)
    match = pattern.search(text)
    if not match:
        raise SystemExit("Pinned Stanford generation layout changed")
    replacement = '''def gpt_request(prompt: str,
                model: str = "community-bitnet",
                max_tokens: int = 1500) -> str:
  # COMMUNITY_BITNET_CHAT_V7; COMMUNITY_BITNET_HTTP_V4 compatibility marker.
  try:
    import json
    import os
    import urllib.request
    port = int(os.environ.get("COMMUNITY_BITNET_PORT", "8080"))
    payload = json.dumps({
      "model": model,
      "messages": [
        {"role": "system", "content": prompt},
      ],
      "max_tokens": min(int(max_tokens), max(128, int(os.environ.get("COMMUNITY_MAX_TOKENS", "96")))),
      "temperature": 0.7,
      "top_p": 0.9,
      "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=int(os.environ.get("COMMUNITY_GENERATION_TIMEOUT", "900"))) as response:
      data = json.loads(response.read().decode("utf-8"))
    choices = data.get("choices") if isinstance(data, dict) else None
    message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str) or not content.strip():
      raise RuntimeError(f"BitNet chat-completions endpoint returned no usable content: {data!r}")
    return content.strip()
  except Exception as e:
    return f"GENERATION ERROR: {str(e)}"


def chat_safe_generate(prompt_input: Union[str, List[str]],
                       prompt_lib_file: str,
                       gpt_version: str = "community-bitnet",
                       repeat: int = 1,
                       fail_safe = "error",
                       func_clean_up: callable = None,
                       verbose: bool = False,
                       max_tokens: int = 1500,
                       file_attachment: str = None,
                       file_type: str = None) -> tuple:
  # Generate with local BitNet while preserving Stanford's helper contract.
  if file_attachment or file_type:
    raise RuntimeError("Community local BitNet path does not support attachments.")
  prompt = generate_prompt(prompt_input, prompt_lib_file)
  response = fail_safe
  attempts = max(1, int(repeat))
  for i in range(attempts):
    response = gpt_request(prompt, model=gpt_version, max_tokens=max_tokens)
    if not (isinstance(response, str) and response.startswith("GENERATION ERROR:")):
      break
    if i + 1 < attempts:
      time.sleep(2**i)
  if isinstance(response, str) and response.startswith("GENERATION ERROR:"):
    raise RuntimeError(response)
  if func_clean_up:
    response = func_clean_up(response, prompt=prompt)
  if verbose or DEBUG:
    print_run_prompts(prompt_input, prompt, response)
  return response, prompt, prompt_input, fail_safe

'''
    text = text[:match.start()] + replacement + text[match.end():]

    emb_pattern = re.compile(r"def get_text_embedding\(.*?(?=\n(?:def |class )|\Z)", re.S)
    emb_match = emb_pattern.search(text)
    if not emb_match:
        raise SystemExit("Pinned Stanford embedding layout changed")
    emb_replacement = '''def get_text_embedding(text: str,
                       model: str = "local-hash") -> List[float]:
  # Generate a deterministic local embedding without any external API.
  if not isinstance(text, str) or not text.strip():
    raise ValueError("Input text must be a non-empty string.")
  import hashlib
  import math
  import re
  dims = 256
  vector = [0.0] * dims
  for token in re.findall(r"\\w+", text.lower()):
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    index = int.from_bytes(digest[:4], "big") % dims
    vector[index] += 1.0 if digest[4] & 1 else -1.0
  norm = math.sqrt(sum(value * value for value in vector)) or 1.0
  return [value / norm for value in vector]
'''
    text = text[:emb_match.start()] + emb_replacement + text[emb_match.end():]
    path.write_text(text, encoding="utf-8")


def patch_utterance_prompt() -> None:
    'Replace Stanford fictional-character framing with direct peer speech.'
    path = (
        STANFORD
        / "simulation_engine"
        / "prompt_template"
        / "generative_agent"
        / "interaction"
        / "utternace"
        / "utterance_v1.txt"
    )
    text = path.read_text(encoding="utf-8")
    marker = "COMMUNITY_PEER_UTTERANCE_V1"
    if marker in text:
        return
    if (
        "fictional subject above" not in text
        or "We are writing a dialogue between the subject above, and me." not in text
        or '{"utterance": "[...]"}' not in text
    ):
        raise SystemExit(f"Pinned Stanford utterance prompt changed; patch target not found in {path}")

    prompt = '''### COMMUNITY_PEER_UTTERANCE_V1
<commentblockmarker>###</commentblockmarker>
<Background information about the speaker>
!<INPUT 0>!

<End of background information about the speaker>
=====
<Current private conversation context>
!<INPUT 1>!

<End of current private conversation context>
=====
<Dialogue so far>
!<INPUT 2>!

<End of dialogue so far>

Task: The next line belongs to the speaker described above. Continue the private conversation from that speaker's first-person perspective. Stay with what the other person just said, use the speaker's own memories and current state, and carry the conversation forward in the speaker's own words rather than restating the other person's sentence.

Output format -- output your response in json:
{"utterance": "[...]"}'''
    path.write_text(prompt, encoding="utf-8")


def patch_memory() -> None:
    path = STANFORD / "genagents" / "modules" / "memory_stream.py"
    pristine = '''  def _func_clean_up(gpt_response, prompt=""): 
    gpt_response = extract_first_json_dict(gpt_response)
    return list(gpt_response.values())

  def _get_fail_safe():
    return 25
'''
    previous_patch = '''  def _func_clean_up(gpt_response, prompt=""): 
    gpt_response = extract_first_json_dict(gpt_response)
    if not isinstance(gpt_response, dict):
      return [25 for _ in records]
    values = list(gpt_response.values())
    if len(values) != len(records):
      return [25 for _ in records]
    return values

  def _get_fail_safe():
    return [25 for _ in records]
'''
    numeric_patch = '''  def _func_clean_up(gpt_response, prompt=""): 
    gpt_response = extract_first_json_dict(gpt_response)
    if not isinstance(gpt_response, dict):
      return [25 for _ in records]
    values = list(gpt_response.values())
    if len(values) != len(records):
      return [25 for _ in records]
    cleaned = []
    for value in values:
      try:
        score = float(value)
      except (TypeError, ValueError):
        score = 25.0
      cleaned.append(max(0.0, min(100.0, score)))
    return cleaned

  def _get_fail_safe():
    return [25 for _ in records]
'''
    replace_one_of(
        path,
        (pristine, previous_patch),
        numeric_patch,
        "cleaned.append(max(0.0, min(100.0, score)))",
    )
    replace_once(
        path,
        '''  def _func_clean_up(gpt_response, prompt=""): 
    return extract_first_json_dict(gpt_response)["reflection"]

  def _get_fail_safe():
    return []
''',
        '''  def _func_clean_up(gpt_response, prompt=""): 
    if isinstance(gpt_response, str) and gpt_response.strip().startswith("GENERATION ERROR:"):
      raise RuntimeError(gpt_response.strip())
    parsed = extract_first_json_dict(gpt_response)
    if isinstance(parsed, dict):
      reflection = parsed.get("reflection")
      if isinstance(reflection, list):
        return reflection[:reflection_count]
      if isinstance(reflection, str) and reflection.strip():
        return [reflection.strip()]
    if isinstance(gpt_response, str) and gpt_response.strip():
      return [gpt_response.strip()[:1000]]
    return []

  def _get_fail_safe():
    return []
''',
        "return [gpt_response.strip()[:1000]]",
    )


def patch_interaction() -> None:
    path = STANFORD / "genagents" / "modules" / "interaction.py"
    replace_once(
        path,
        '''  def _func_clean_up(gpt_response, prompt=""): 
    utterance = extract_first_json_dict(gpt_response)["utterance"]
    return utterance

  def _get_fail_safe():
    return None
''',
        '''  def _func_clean_up(gpt_response, prompt=""): 
    if isinstance(gpt_response, str) and gpt_response.strip().startswith("GENERATION ERROR:"):
      raise RuntimeError(gpt_response.strip())
    parsed = extract_first_json_dict(gpt_response)
    if isinstance(parsed, dict):
      utterance = parsed.get("utterance")
      if isinstance(utterance, str) and utterance.strip():
        return utterance.strip()
    if isinstance(gpt_response, str) and gpt_response.strip():
      return gpt_response.strip()[:1000]
    raise RuntimeError("Model returned no usable utterance.")

  def _get_fail_safe():
    return None
''',
        "Model returned no usable utterance.",
    )


def main() -> None:
    if not STANFORD.exists():
        raise SystemExit("Stanford runtime is not present")
    patch_gpt()
    patch_utterance_prompt()
    patch_memory()
    patch_interaction()
    print("Stanford runtime patched for Falcon-native local BitNet generation.")


if __name__ == "__main__":
    main()
