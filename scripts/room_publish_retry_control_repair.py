#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if new in text:
        print(f'PASS: {path} already repaired')
        return
    if text.count(old) != 1:
        raise SystemExit(f'FAIL: guarded source mismatch in {path}')
    p.write_text(text.replace(old, new, 1))
    print(f'PASS: repaired {path}')


replace_once(
    'scripts/room_expression_quality_core.py',
    '''import hashlib\nimport os\nimport re\n\nimport room_private_model as _private_model\n''',
    '''import hashlib\nimport json\nimport os\nimport re\nfrom pathlib import Path\n\nimport room_private_model as _private_model\n''',
)

replace_once(
    'scripts/room_expression_quality_core.py',
    '''def _strip_retry_prose(prompt: object) -> str:\n    \"\"\"Retry control is internal state; never expose it as model-visible prose.\"\"\"\n    return str(prompt or \"\").replace(_RETRY_PROSE, \"\")\n''',
    '''PUBLISH_RETRY_MARKER = Path(\".room-publish-retry.json\")\n\n\ndef _publish_retry_control(reason: object) -> str:\n    reason = str(reason or \"\").lower()\n    if \"same_beat_sentence_copy\" in reason or \"same_beat_phrase_echo\" in reason or \"semantic_phrase_mosaic\" in reason:\n        return (\n            \"\\nWHOLE-BEAT RETRY CONTROL: Your previous staged reply overlapped too closely with speech already in this beat. \"\n            \"Use a new proposition and entirely fresh phrasing; do not reuse a complete sentence, clause, or distinctive phrase.\"\n        )\n    if \"same_beat_semantic_coverage\" in reason or \"same_beat_restatement_sentence\" in reason or \"same_beat_short_echo\" in reason or \"same_beat_low_novelty\" in reason:\n        return (\n            \"\\nWHOLE-BEAT RETRY CONTROL: Your previous staged reply restated a contribution already made in this beat. \"\n            \"Advance the conversation with a different consequence, example, question, disagreement, or concrete implication.\"\n        )\n    return (\n        \"\\nWHOLE-BEAT RETRY CONTROL: Your previous staged reply failed the final novelty check. \"\n        \"Make one genuinely new contribution in fresh wording.\"\n    )\n\n\ndef _inject_publish_retry_control(prompt: object, self_entity: object, path: Path | None = None) -> str:\n    text = str(prompt or \"\")\n    marker = Path(path) if path is not None else PUBLISH_RETRY_MARKER\n    try:\n        payload = json.loads(marker.read_text())\n    except Exception:\n        return text\n    if not isinstance(payload, dict):\n        return text\n    entity = str(payload.get(\"entity\") or \"\").lower()\n    if entity and entity != str(self_entity or \"\").lower():\n        return text\n    reason = str(payload.get(\"reason\") or \"\").strip()\n    if not reason:\n        return text\n    guidance = _publish_retry_control(reason)\n    for separator in (\"\\nSITUATION_DATA\\n\", \"\\nCONVERSATION\\n\"):\n        if separator in text:\n            control, situation = text.split(separator, 1)\n            return control + guidance + separator + situation\n    return text\n\n\ndef _strip_retry_prose(prompt: object) -> str:\n    \"\"\"Retry control is internal state; never expose it as model-visible prose.\"\"\"\n    return str(prompt or \"\").replace(_RETRY_PROSE, \"\")\n''',
)

replace_once(
    'scripts/room_expression_quality_core.py',
    '''        request_prompt = str(prompt or \"\")\n        if role != \"expression\":\n            request_prompt = _strip_retry_prose(request_prompt)\n''',
    '''        request_prompt = str(prompt or \"\")\n        if role == \"expression\":\n            request_prompt = _inject_publish_retry_control(request_prompt, self_entity)\n        else:\n            request_prompt = _strip_retry_prose(request_prompt)\n''',
)

replace_once(
    'scripts/room_private_commit_liveness_core.py',
    '''import re\nimport sys\n\nimport room_private_commit_base as _base\n''',
    '''import json\nimport re\nimport sys\nfrom pathlib import Path\n\nimport room_private_commit_base as _base\n''',
)

replace_once(
    'scripts/room_private_commit_liveness_core.py',
    '''def _run_cli() -> None:\n    try:\n        c.main()\n    except RuntimeError as exc:\n        code = quality_rejection_exit_code(exc)\n        if code is None:\n            raise\n        print(f\"ROOM PUBLISH QUALITY REJECTION: {exc}\", file=sys.stderr)\n        raise SystemExit(code) from None\n''',
    '''PUBLISH_RETRY_MARKER = Path(\".room-publish-retry.json\")\n\n\ndef record_publish_retry_marker(error: BaseException, path: Path | None = None) -> dict | None:\n    match = re.search(r\"private Room same-beat echo blocked for ([a-z]+): ([a-z0-9_]+)\", str(error), re.I)\n    if not match:\n        return None\n    payload = {\"entity\": match.group(1).lower(), \"reason\": match.group(2).lower()}\n    marker = Path(path) if path is not None else PUBLISH_RETRY_MARKER\n    marker.write_text(json.dumps(payload, sort_keys=True) + \"\\n\")\n    return payload\n\n\ndef _run_cli() -> None:\n    try:\n        c.main()\n    except RuntimeError as exc:\n        code = quality_rejection_exit_code(exc)\n        if code is None:\n            raise\n        record_publish_retry_marker(exc)\n        print(f\"ROOM PUBLISH QUALITY REJECTION: {exc}\", file=sys.stderr)\n        raise SystemExit(code) from None\n''',
)

replace_once(
    'scripts/room_private_commit.py',
    '''QUALITY_REJECTION_COUNTER = Path(\".room-quality-rejections\")\nMAX_CONSECUTIVE_QUALITY_REJECTIONS = 3\n''',
    '''QUALITY_REJECTION_COUNTER = Path(\".room-quality-rejections\")\nPUBLISH_RETRY_MARKER = Path(\".room-publish-retry.json\")\nMAX_CONSECUTIVE_QUALITY_REJECTIONS = 3\n''',
)

replace_once(
    'scripts/room_private_commit.py',
    '''def _clear_quality_rejections() -> None:\n    try:\n        QUALITY_REJECTION_COUNTER.unlink()\n    except FileNotFoundError:\n        pass\n''',
    '''def _clear_quality_rejections() -> None:\n    try:\n        QUALITY_REJECTION_COUNTER.unlink()\n    except FileNotFoundError:\n        pass\n\n\ndef clear_publish_retry_marker(path: Path | None = None) -> None:\n    marker = Path(path) if path is not None else PUBLISH_RETRY_MARKER\n    try:\n        marker.unlink()\n    except FileNotFoundError:\n        pass\n''',
)

replace_once(
    'scripts/room_private_commit.py',
    '''    else:\n        _clear_quality_rejections()\n''',
    '''    else:\n        _clear_quality_rejections()\n        clear_publish_retry_marker()\n''',
)
