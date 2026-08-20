#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "scripts" / "room_engine_v5.py"


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
        ENGINE,
        '    "expression": (\n'
        '        "Write this person\'s next natural conversational reply. Ground it in the newest spoken line when there "\n'
        '        "is one. Let personality shape perspective and tone. Keep it concise, usually one to three sentences, "\n'
        '        "and add something that has not already been said."\n'
        '    ),\n',
        '    "expression": (\n'
        '        "Write this person\'s next natural conversational reply. Treat the newest spoken line as a real turn "\n'
        '        "that deserves a reaction before introducing a new angle. If someone just questioned, contradicted, "\n'
        '        "supported, teased, challenged, or added to a point, respond to that social meaning naturally. Let "\n'
        '        "personality shape perspective and tone. Keep it concise, usually one to three sentences, and add "\n'
        '        "something that has not already been said."\n'
        '    ),\n',
        "responsive expression instruction",
    )

    replace_once(
        ENGINE,
        'def _second_voice_engages_allen(key):\n'
        '    """Deterministic 75% gate so beat retries preserve the same routing."""\n'
        '    return hashlib.sha256(f"allen-second-voice:{key}".encode()).digest()[0] < 192\n',
        'def _allen_voice_engages(key, rank):\n'
        '    """Deterministic ordinary-turn engagement with natural falloff by rank."""\n'
        '    thresholds = {0: 256, 1: 230, 2: 175, 3: 105}\n'
        '    threshold = thresholds.get(int(rank), 0)\n'
        '    if threshold >= 256:\n'
        '        return True\n'
        '    return hashlib.sha256(f"allen-responsive:{rank}:{key}".encode()).digest()[0] < threshold\n',
        "broader Allen engagement gate",
    )

    replace_once(
        ENGINE,
        '# The expression phase is sequential. Rank 0 always answers Allen when Allen is\n'
        '# the latest public event. Rank 1 stays with Allen on a deterministic 75% gate,\n'
        '# which makes two responders usual without turning every interruption into a\n'
        '# four-voice chorus. Ranks 2-3 remain unconstrained.\n',
        '# The expression phase is sequential. Ordinary Allen turns usually hold roughly\n'
        '# three voices: rank 0 always, then deterministic falloff across ranks 1-3. A\n'
        '# provocative Allen turn remains salient to all four. When a voice does move on,\n'
        '# it follows the newest same-beat speaker with a matching relationship frame.\n',
        "responsiveness routing comment",
    )

    replace_once(
        ENGINE,
        '        source = _core.rp(bus_data, entity, role) if role == "expression" else None\n'
        '        base = (source or {}).get("private") or {}\n'
        '        latest = base.get("event") if isinstance(base.get("event"), dict) else None\n',
        '        source = _core.rp(bus_data, entity, role) if role == "expression" else None\n'
        '        base = (source or {}).get("private") or {}\n'
        '        latest = base.get("event") if isinstance(base.get("event"), dict) else None\n'
        '        prior_same_beat = _core.prior_expression_messages(node) if role == "expression" else []\n',
        "capture same-beat replies",
    )

    replace_once(
        ENGINE,
        '        primary_allen_reply = bool(allen_latest and rank == 0)\n'
        '        secondary_allen_reply = bool(\n'
        '            allen_latest\n'
        '            and rank == 1\n'
        '            and (provocative_allen_turn or _second_voice_engages_allen(key))\n'
        '        )\n'
        '        late_allen_reply = bool(allen_latest and rank >= 2 and provocative_allen_turn)\n'
        '        routed_allen_reply = primary_allen_reply or secondary_allen_reply or late_allen_reply\n',
        '        primary_allen_reply = bool(allen_latest and rank == 0)\n'
        '        secondary_allen_reply = bool(\n'
        '            allen_latest\n'
        '            and rank == 1\n'
        '            and (provocative_allen_turn or _allen_voice_engages(key, rank))\n'
        '        )\n'
        '        late_allen_reply = bool(\n'
        '            allen_latest\n'
        '            and rank >= 2\n'
        '            and (provocative_allen_turn or _allen_voice_engages(key, rank))\n'
        '        )\n'
        '        routed_allen_reply = primary_allen_reply or secondary_allen_reply or late_allen_reply\n',
        "ordinary Allen engagement across later voices",
    )

    replace_once(
        ENGINE,
        '        provocative_allen_turn = False\n        entity = None\n\n    if not routed_allen_reply:\n        return _original_recurrent(node, key, bus_data)\n',
        '        provocative_allen_turn = False\n        prior_same_beat = []\n        entity = None\n\n'
        '    if not routed_allen_reply:\n'
        '        # Core expression generation already makes the newest same-beat\n'
        '        # utterance the current event. Keep partner and relationship context\n'
        '        # aligned with that same speaker instead of an older public partner.\n'
        '        if role == "expression" and prior_same_beat:\n'
        '            newest = prior_same_beat[-1] if isinstance(prior_same_beat[-1], dict) else {}\n'
        '            responsive_partner = str(newest.get("speaker") or "").lower()\n'
        '            if responsive_partner in _AI_ORDER and responsive_partner != entity:\n'
        '                responsive_bus = copy.deepcopy(bus_data)\n'
        '                responsive_source = _core.rp(responsive_bus, entity, role)\n'
        '                responsive_base = responsive_source.get("private") if isinstance(responsive_source.get("private"), dict) else {}\n'
        '                responsive_base["partner"] = responsive_partner\n'
        '                try:\n'
        '                    rel = _core.minds()["entities"][entity]["people"][responsive_partner]\n'
        '                    responsive_base["relationship"] = {\n'
        '                        k: rel.get(k) for k in (\n'
        '                            "exposure", "direct_familiarity", "trust", "predictability",\n'
        '                            "reciprocity", "warmth", "respect", "disclosure_depth", "tension"\n'
        '                        )\n'
        '                    }\n'
        '                except Exception:\n'
        '                    pass\n'
        '                thought = ((responsive_bus.get("recurrent", {}).get(entity, {}) or {}).get("thought", {}) or {})\n'
        '                thought_private = thought.get("private") if isinstance(thought.get("private"), dict) else {}\n'
        '                deliberation = thought_private.get("deliberation") if isinstance(thought_private.get("deliberation"), dict) else None\n'
        '                if isinstance(deliberation, dict):\n'
        '                    deliberation["preferred_partner"] = responsive_partner\n'
        '                return _original_recurrent(node, key, responsive_bus)\n'
        '        return _original_recurrent(node, key, bus_data)\n',
        "align same-beat partner and relationship",
    )

    print("Room responsiveness repair applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
