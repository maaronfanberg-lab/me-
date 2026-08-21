#!/usr/bin/env python3
from pathlib import Path

# Re-pushed after the workflow file existed so the branch-scoped repair job runs.
path = Path(__file__).resolve().parent / "room_expression_quality.py"
text = path.read_text()
anchor = '''def _substantial_sentence_copy(utterance: str, prior_turns: list[dict]) -> bool:\n'''
helper = '''def _authoritative_same_beat_prior_turns(compact: dict) -> list[dict]:\n    \"\"\"Prefer the actual spoken parts for this expression process.\n\n    The compact prompt context is lossy by design. Production must not let that\n    lossy copy define the publication-quality boundary when `room_parts` still\n    contains the exact turns already spoken in this beat.\n    \"\"\"\n    fallback = _same_beat_prior_turns(compact)\n    try:\n        node = int(os.environ.get(\"ROOM_NODE_ID\", \"-1\"))\n    except Exception:\n        return fallback\n    if node < 0:\n        return fallback\n    try:\n        import room_engine_v5_core as _core\n        live = _core.prior_expression_messages(node)\n    except Exception:\n        live = []\n    out: list[dict] = []\n    for item in live if isinstance(live, list) else []:\n        if not isinstance(item, dict):\n            continue\n        if str(item.get(\"speaker\") or \"\").lower() not in _AUTONOMOUS:\n            continue\n        if not str(item.get(\"text\") or \"\").strip():\n            continue\n        out.append(item)\n    return out or fallback\n\n\n'''
if helper not in text:
    if anchor not in text:
        raise SystemExit("quality helper anchor missing")
    text = text.replace(anchor, helper + anchor, 1)
text = text.replace('    same_beat = _same_beat_prior_turns(compact)\n    if same_beat:\n        compact["context"] = [dict(item) for item in same_beat]\n', '    same_beat = _authoritative_same_beat_prior_turns(compact)\n    if same_beat:\n        compact["context"] = [dict(item) for item in same_beat]\n', 1)
text = text.replace('    same_beat = _same_beat_prior_turns(compact)\n    if same_beat and _substantial_sentence_copy(text, same_beat):\n', '    same_beat = _authoritative_same_beat_prior_turns(compact)\n    if same_beat and _substantial_sentence_copy(text, same_beat):\n', 1)
path.write_text(text)
print("authoritative live-parts quality repair applied")
