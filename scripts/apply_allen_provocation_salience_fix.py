#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "scripts" / "room_engine_v5.py"
PERSONALITY = ROOT / "scripts" / "room_personality_v2.py"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    if new in text:
        print(f"already applied: {label}")
        return
    if old not in text:
        raise SystemExit(f"repair anchor missing: {label}")
    path.write_text(text.replace(old, new, 1))
    print(f"applied: {label}")


def main() -> int:
    replace_once(
        PERSONALITY,
        '_CRITICISM_RE = re.compile(r"\\b(wrong|nonsense|stupid|bad argument|makes no sense|ridiculous|idiot)\\b")\n',
        '_CRITICISM_RE = re.compile(r"\\b(wrong|nonsense|stupid|bad argument|makes no sense|ridiculous|idiot)\\b")\n'
        '_CHALLENGE_RE = re.compile(r"\\b(prove it|try me|i dare you|dare you|you can\\\'t|you cannot|make me|delete you|shut you down|bet you won\\\'t|bet you can\\\'t)\\b")\n'
        '_CONTRADICTION_RE = re.compile(r"\\b(that\\\'s false|that is false|not true|you\\\'re wrong|you are wrong|the opposite|can\\\'t be true|cannot be true|impossible|i disagree)\\b")\n\n'
        'def _contradiction_or_challenge(text: str) -> bool:\n'
        '    low = _norm(text)\n'
        '    if _CHALLENGE_RE.search(low) or _CONTRADICTION_RE.search(low):\n'
        '        return True\n'
        '    # Treat an explicitly false numeric equality as a contradiction, not\n'
        '    # as an ignorable fragment. This catches compact probes such as 0=1.\n'
        '    for match in re.finditer(r"(?<![\\w.])(-?\\d+(?:\\.\\d+)?)\\s*=\\s*(-?\\d+(?:\\.\\d+)?)(?![\\w.])", low):\n'
        '        try:\n'
        '            if float(match.group(1)) != float(match.group(2)):\n'
        '                return True\n'
        '        except ValueError:\n'
        '            pass\n'
        '    # A direct self-negation ("X is not X") is also inherently salient.\n'
        '    if re.search(r"\\b([a-z][a-z\\\'-]{2,})\\s+(?:is|are)\\s+not\\s+\\1\\b", low):\n'
        '        return True\n'
        '    return False\n',
        "personality contradiction detector",
    )

    replace_once(
        PERSONALITY,
        '    if _CRITICISM_RE.search(text):\n        labels.append("criticism_or_rejection")\n',
        '    if _CRITICISM_RE.search(text):\n        labels.append("criticism_or_rejection")\n'
        '    if _contradiction_or_challenge(text):\n'
        '        labels.append("contradiction_or_challenge")\n',
        "personality contradiction label",
    )

    replace_once(
        PERSONALITY,
        '    if "evidence_request" in labels:\n        lenses.append(str(profile.get("evidence_style", "")))\n',
        '    if "evidence_request" in labels:\n        lenses.append(str(profile.get("evidence_style", "")))\n'
        '    if "contradiction_or_challenge" in labels:\n'
        '        lenses.extend([str(profile.get("disagreement_style", "")), str(profile.get("evidence_style", ""))])\n',
        "personality contradiction lens",
    )

    replace_once(
        PERSONALITY,
        '        for label in ("greeting", "question", "topic_bid", "evidence_request", "repair_bid")\n',
        '        for label in ("greeting", "question", "topic_bid", "evidence_request", "repair_bid", "contradiction_or_challenge")\n',
        "personality contradiction salience",
    )

    replace_once(
        PERSONALITY,
        '    if "fragment_or_ambiguous" in labels and "question" not in labels:\n        priority = "clarify_or_interpret_fragment"\n',
        '    if (\n'
        '        "fragment_or_ambiguous" in labels\n'
        '        and "question" not in labels\n'
        '        and "contradiction_or_challenge" not in labels\n'
        '    ):\n'
        '        priority = "clarify_or_interpret_fragment"\n',
        "contradiction beats fragment fallback",
    )

    replace_once(
        ENGINE,
        '\ndef _second_voice_engages_allen(key):\n',
        '\n_ALLEN_PROVOCATION_LABELS = frozenset({\n'
        '    "contradiction_or_challenge",\n'
        '    "criticism_or_rejection",\n'
        '    "exclusion",\n'
        '})\n\n\n'
        'def _allen_turn_is_provocative(event, context=None):\n'
        '    """Keep a genuinely challenging Allen turn salient for the whole beat."""\n'
        '    if not isinstance(event, dict) or str(event.get("speaker") or "").lower() != "allen":\n'
        '        return False\n'
        '    labels = set(_personality_v2.classify_event(event, context if isinstance(context, list) else []))\n'
        '    return bool(labels & _ALLEN_PROVOCATION_LABELS)\n\n\n'
        'def _second_voice_engages_allen(key):\n',
        "engine provocation classifier",
    )

    replace_once(
        ENGINE,
        '        primary_allen_reply = bool(allen_latest and rank == 0)\n'
        '        secondary_allen_reply = bool(allen_latest and rank == 1 and _second_voice_engages_allen(key))\n'
        '        routed_allen_reply = primary_allen_reply or secondary_allen_reply\n',
        '        provocative_allen_turn = bool(\n'
        '            allen_latest and _allen_turn_is_provocative(latest, base.get("context"))\n'
        '        )\n'
        '        primary_allen_reply = bool(allen_latest and rank == 0)\n'
        '        secondary_allen_reply = bool(\n'
        '            allen_latest\n'
        '            and rank == 1\n'
        '            and (provocative_allen_turn or _second_voice_engages_allen(key))\n'
        '        )\n'
        '        late_allen_reply = bool(allen_latest and rank >= 2 and provocative_allen_turn)\n'
        '        routed_allen_reply = primary_allen_reply or secondary_allen_reply or late_allen_reply\n',
        "route provocation through all voices",
    )

    replace_once(
        ENGINE,
        '        secondary_allen_reply = False\n        entity = None\n',
        '        secondary_allen_reply = False\n        late_allen_reply = False\n        provocative_allen_turn = False\n        entity = None\n',
        "safe provocation fallback",
    )

    replace_once(
        ENGINE,
        '    if secondary_allen_reply:\n        _core.prior_expression_messages = lambda _node: []\n',
        '    if secondary_allen_reply or late_allen_reply:\n'
        '        # Later voices must still see Allen\'s challenging line itself, not\n'
        '        # the first AI reply that would otherwise replace it sequentially.\n'
        '        _core.prior_expression_messages = lambda _node: []\n',
        "preserve provocative event for later voices",
    )

    print("Allen provocation salience repair applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
