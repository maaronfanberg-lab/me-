#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parent / "room_expression_quality.py"
text = path.read_text()

function_anchor = '''def _anchor_tokens(text: object) -> set[str]:\n'''
function_block = '''def _short_content_tokens(text: object) -> set[str]:\n    out: set[str] = set()\n    for raw in _tokens(text):\n        if raw in _NOVELTY_STOP:\n            continue\n        word = _stem(raw)\n        if word:\n            out.add(word)\n    return out\n\n\ndef _short_same_beat_paraphrase(utterance: str, prior_turns: list[dict]) -> bool:\n    \"\"\"Reject brief restatements of the immediately preceding statement.\n\n    Tiny acknowledgements such as \"I agree\" remain legal. Direct questions are\n    also excluded here because concise answers may legitimately reuse their terms.\n    \"\"\"\n    if not prior_turns:\n        return False\n    previous = str((prior_turns[-1] or {}).get(\"text\") or \"\").strip()\n    if not previous or \"?\" in previous:\n        return False\n    current = _short_content_tokens(utterance)\n    earlier = _short_content_tokens(previous)\n    shortest = min(len(current), len(earlier))\n    if shortest < 2 or shortest > 10:\n        return False\n    overlap = len(current & earlier)\n    containment = overlap / max(1, shortest)\n    novel = current - earlier\n    return containment >= 0.80 and len(novel) <= 1 and len(current) <= len(earlier) + 1\n\n\n'''
if "def _short_same_beat_paraphrase" not in text:
    if function_anchor not in text:
        raise SystemExit("function anchor missing")
    text = text.replace(function_anchor, function_block + function_anchor, 1)

old = '''    if same_beat and _substantial_sentence_copy(text, same_beat):\n        _escape_stale_context(compact, self_entity)\n        return \"same_beat_sentence_copy\"\n    if same_beat and _low_substantive_novelty(text, same_beat):\n        _escape_stale_context(compact, self_entity)\n        return \"same_beat_low_novelty\"\n'''
new = '''    if same_beat and _substantial_sentence_copy(text, same_beat):\n        return \"same_beat_sentence_copy\"\n    if same_beat and _short_same_beat_paraphrase(text, same_beat):\n        return \"same_beat_short_echo\"\n    if same_beat and _low_substantive_novelty(text, same_beat):\n        return \"same_beat_low_novelty\"\n'''
if new not in text:
    if old not in text:
        raise SystemExit("quality anchor missing")
    text = text.replace(old, new, 1)

path.write_text(text)
print("short same-beat echo repair applied")
