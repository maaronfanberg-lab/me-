#!/usr/bin/env python3
from pathlib import Path


def replace_exact(path, old, new, expected=1):
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"FAIL: {path}: expected {expected} exact match(es), found {count}")
    p.write_text(text.replace(old, new, expected))
    print(f"PATCH {path}: {count} exact match(es)")

# 1) Expression quality: log the actual colliding pair and exclude that prior
# sentence from model-visible retry context while the authoritative same-beat
# gate still sees the exact staged turn from room_parts.
q = "scripts/room_expression_quality_core.py"
replace_exact(q, "import re\nfrom pathlib import Path\n", "import re\nimport sys\nfrom pathlib import Path\n")
anchor = '''def same_beat_issue(utterance: object, prior_turns: list[dict]) -> str | None:\n'''
helper = r'''def collision_detail(utterance: object, prior_turns: list[dict]) -> dict | None:
    current_sentences = _sentences(utterance)
    best = None
    best_score = -1.0
    for turn in prior_turns or []:
        if not isinstance(turn, dict):
            continue
        for current in current_sentences:
            current_tokens = set(_tokens(current))
            if not current_tokens:
                continue
            for earlier in _sentences(turn.get("text")):
                earlier_tokens = set(_tokens(earlier))
                if not earlier_tokens:
                    continue
                overlap = len(current_tokens & earlier_tokens)
                score = overlap / max(1, len(current_tokens | earlier_tokens))
                if score > best_score:
                    best_score = score
                    best = {
                        "current_sentence": current,
                        "prior_sentence": earlier,
                        "prior_speaker": str(turn.get("speaker") or "").strip().lower(),
                        "score": round(score, 6),
                    }
    return best


def _exclude_collided_sentence(compact: dict, detail: dict | None) -> None:
    if not detail:
        return
    collided = str(detail.get("prior_sentence") or "").strip()
    if not collided:
        return
    context = compact.get("context") if isinstance(compact.get("context"), list) else []
    cleaned = []
    for item in context:
        if not isinstance(item, dict):
            cleaned.append(item)
            continue
        copy = dict(item)
        sentences = _sentences(copy.get("text"))
        kept = [sentence for sentence in sentences if sentence != collided]
        if kept:
            copy["text"] = " ".join(kept)
            cleaned.append(copy)
    compact["context"] = cleaned
    event = compact.get("event")
    if isinstance(event, dict):
        event_copy = dict(event)
        kept = [sentence for sentence in _sentences(event_copy.get("text")) if sentence != collided]
        compact["event"] = ({**event_copy, "text": " ".join(kept)} if kept else (cleaned[-1] if cleaned else None))


''' + anchor
replace_exact(q, anchor, helper)
replace_exact(q,
'''    same_beat_problem = same_beat_issue(text, same_beat)\n    if same_beat_problem:\n        return same_beat_problem\n''',
'''    same_beat_problem = same_beat_issue(text, same_beat)\n    if same_beat_problem:\n        detail = collision_detail(text, same_beat)\n        if detail:\n            print(\n                "ROOM QUALITY COLLISION "\n                f"issue={same_beat_problem} current_speaker={self_entity or ''} "\n                f"current={detail['current_sentence']!r} prior_speaker={detail['prior_speaker']} "\n                f"prior={detail['prior_sentence']!r}",\n                file=sys.stderr,\n            )\n        if os.environ.get("ROOM_DEGRADE_QUALITY") == "1":\n            _exclude_collided_sentence(compact, detail)\n        return same_beat_problem\n''')

# 2) Per-turn degradation after the existing 9-attempt expression budget.
core = "scripts/room_engine_v5_core.py"
replace_exact(core, "import re\nfrom datetime", "import re\nimport sys\nfrom datetime")
old_call = '''        expression = model_run("expression", {\n            "entity": entity,\n            "profile": P[entity],\n            "social_observation": perception,\n            "deliberation": deliberation,\n            "conversation_job": job,\n            "event": expression_context[-1] if expression_context else (None if collapsed else base.get("event")),\n            "context": expression_context,\n            "topic": expression_topic,\n            "partner": base.get("partner"),\n            "relationship": base.get("relationship"),\n            "mandatory_speech": True,\n        })\n'''
new_call = '''        try:\n            expression = model_run("expression", {\n                "entity": entity,\n                "profile": P[entity],\n                "social_observation": perception,\n                "deliberation": deliberation,\n                "conversation_job": job,\n                "event": expression_context[-1] if expression_context else (None if collapsed else base.get("event")),\n                "context": expression_context,\n                "topic": expression_topic,\n                "partner": base.get("partner"),\n                "relationship": base.get("relationship"),\n                "mandatory_speech": True,\n            })\n        except RuntimeError as exc:\n            prefix = "private model output rejected for expression:"\n            if os.environ.get("ROOM_DEGRADE_QUALITY") != "1" or prefix not in str(exc):\n                raise\n            reason = str(exc).split(prefix, 1)[1].strip() or "quality_rejection"\n            expression = {\n                "decision": "SPEAK",\n                "target": base.get("partner"),\n                "move": "deepen",\n                "utterance": "",\n                "semantic_terms": [],\n                "quality_dropped": reason,\n            }\n            print(f"ROOM DEGRADED TURN DROP: speaker={entity} reason={reason}", file=sys.stderr)\n'''
replace_exact(core, old_call, new_call)

# 3) Publication degrades only the offending staged turn; successful speakers stay.
commit = "scripts/room_private_commit_base.py"
replace_exact(commit, "import re\nfrom datetime", "import os\nimport re\nimport sys\nfrom datetime")
anchor2 = '''def private_commit(parts: list[dict], key: str):\n'''
helper2 = r'''def _quality_collision_log(entity: str, text: str, prior: list[dict], issue: str) -> None:
    detail = _quality.collision_detail(text, prior) if hasattr(_quality, "collision_detail") else None
    if detail:
        print(
            "ROOM PUBLISH COLLISION "
            f"issue={issue} current_speaker={entity} current={detail['current_sentence']!r} "
            f"prior_speaker={detail['prior_speaker']} prior={detail['prior_sentence']!r}",
            file=sys.stderr,
        )
    else:
        print(f"ROOM PUBLISH COLLISION issue={issue} current_speaker={entity} pair=unavailable", file=sys.stderr)


def filter_staged_quality(staged: list[tuple[str, str, str, str, list[str]]]) -> list[tuple[str, str, str, str, list[str]]]:
    if os.environ.get("ROOM_DEGRADE_QUALITY") != "1":
        validate_staged_quality(staged)
        return staged
    kept = []
    for item in staged:
        entity, _move, target, text, _terms = item
        try:
            validate_staged_quality([*kept, item])
        except RuntimeError as exc:
            if "private Room same-beat echo blocked" not in str(exc):
                raise
            prior = [{"speaker": e, "text": t, "cognition": {"target": tg}} for e, _m, tg, t, _ts in kept]
            _quality_collision_log(entity, text, prior, str(exc))
            print(f"ROOM DEGRADED TURN DROP: speaker={entity} reason=publish_quality", file=sys.stderr)
            continue
        kept.append(item)
    if not kept:
        raise RuntimeError("Room quality degradation removed every staged speaker")
    return kept


''' + anchor2
replace_exact(commit, anchor2, helper2)
replace_exact(commit,
'''        if not isinstance(expr, dict):\n            raise RuntimeError(f"private Room requires model expression for {entity}; no public fallback is permitted")\n        if not semantic_values(expr):\n            raise RuntimeError(f"private Room expression lacks semantic fields for {entity}")\n        expressions[entity] = expr\n''',
'''        if not isinstance(expr, dict):\n            raise RuntimeError(f"private Room requires model expression for {entity}; no public fallback is permitted")\n        if expr.get("quality_dropped"):\n            expressions[entity] = expr\n            continue\n        if not semantic_values(expr):\n            raise RuntimeError(f"private Room expression lacks semantic fields for {entity}")\n        expressions[entity] = expr\n''')
replace_exact(commit,
'''    for entity in order:\n        expr = expressions[entity]\n        text = c.model_text(expr)\n''',
'''    for entity in order:\n        expr = expressions[entity]\n        if expr.get("quality_dropped"):\n            print(f"ROOM DEGRADED TURN DROP: speaker={entity} reason={expr.get('quality_dropped')}", file=sys.stderr)\n            continue\n        text = c.model_text(expr)\n''')
replace_exact(commit,
'''    validate_staged_quality(staged)\n\n    spoken: list[dict] = []\n''',
'''    staged = filter_staged_quality(staged)\n\n    spoken: list[dict] = []\n''')
replace_exact(commit,
'''    if len(spoken) != 4 or set(speakers) != set(c.ORDER):\n        raise RuntimeError(f"v5 mandatory speech invariant failed: {speakers}")\n''',
'''    if os.environ.get("ROOM_DEGRADE_QUALITY") == "1":\n        if not spoken or len(speakers) != len(set(speakers)) or any(speaker not in c.ORDER for speaker in speakers):\n            raise RuntimeError(f"v5 degraded speech invariant failed: {speakers}")\n    elif len(spoken) != 4 or set(speakers) != set(c.ORDER):\n        raise RuntimeError(f"v5 mandatory speech invariant failed: {speakers}")\n''')
replace_exact(commit,
'''    S.update({\n        "version": c.VERSION,\n''',
'''    S.update({\n        "version": c.VERSION,\n''')
replace_exact(commit,
'''        "note": "research-informed v5 private model active; four mandatory unique speakers; bounded topic episodes; no public fallback; privacy gate retained",\n    })\n''',
'''        "note": "research-informed v5 private model active; quality rejection degrades individual turns; bounded topic episodes; privacy gate retained",\n    })\n    if os.environ.get("ROOM_DEGRADE_QUALITY") == "1":\n        S["heartbeat"] = {"last_successful_beat_at": stamp, "stalled": False}\n''')

# 4) Runner enables Step 0 only after code paths are in place; genuine faults get
# four attempts. Quality drops never reach the legacy whole-beat exit-42 path.
wf = ".github/workflows/sarah-society.yml"
replace_exact(wf, "          ROOM_BEAT_FAILURE_LIMIT=2\n", "          ROOM_BEAT_FAILURE_LIMIT=4\n          export ROOM_DEGRADE_QUALITY=1\n")

print("PASS: guarded Step 0 source patch applied")
