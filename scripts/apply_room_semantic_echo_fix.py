#!/usr/bin/env python3
from pathlib import Path

path = Path(__file__).resolve().parent / "room_expression_quality.py"
text = path.read_text()

anchor = '''def _anchor_tokens(text: object) -> set[str]:\n'''
block = '''def _same_beat_restatement_sentence(utterance: str, prior_turns: list[dict]) -> bool:\n    \"\"\"Reject a substantive sentence that mainly restates a same-beat proposition.\n\n    Brief acknowledgements remain legal, and if the immediately preceding turn is\n    a question this rule stays out of the way so concise direct answers can reuse\n    the question's vocabulary.\n    \"\"\"\n    if not prior_turns:\n        return False\n    previous = str((prior_turns[-1] or {}).get(\"text\") or \"\").strip()\n    if not previous or \"?\" in previous:\n        return False\n    for current_sentence in _sentences(utterance):\n        current = _short_content_tokens(current_sentence)\n        if len(current) < 4:\n            continue\n        for turn in prior_turns:\n            for earlier_sentence in _sentences(turn.get(\"text\")):\n                earlier = _short_content_tokens(earlier_sentence)\n                shortest = min(len(current), len(earlier))\n                if shortest < 4:\n                    continue\n                overlap = len(current & earlier)\n                current_coverage = overlap / max(1, len(current))\n                containment = overlap / max(1, shortest)\n                novel = current - earlier\n                if current_coverage >= 0.78 and containment >= 0.78 and len(novel) <= 2:\n                    return True\n    return False\n\n\n'''
if "def _same_beat_restatement_sentence" not in text:
    if anchor not in text:
        raise SystemExit("semantic echo function anchor missing")
    text = text.replace(anchor, block + anchor, 1)

old = '''    if same_beat and _short_same_beat_paraphrase(text, same_beat):\n        # Keep the conversational context intact so the retry can answer the\n        # same person with a new contribution rather than escaping the topic.\n        return \"same_beat_short_echo\"\n    if same_beat and _low_substantive_novelty(text, same_beat):\n'''
new = '''    if same_beat and _short_same_beat_paraphrase(text, same_beat):\n        # Keep the conversational context intact so the retry can answer the\n        # same person with a new contribution rather than escaping the topic.\n        return \"same_beat_short_echo\"\n    if same_beat and _same_beat_restatement_sentence(text, same_beat):\n        return \"same_beat_restatement_sentence\"\n    if same_beat and _low_substantive_novelty(text, same_beat):\n'''
if new not in text:
    if old not in text:
        raise SystemExit("semantic echo quality anchor missing")
    text = text.replace(old, new, 1)

path.write_text(text)
print("semantic same-beat echo repair applied")
