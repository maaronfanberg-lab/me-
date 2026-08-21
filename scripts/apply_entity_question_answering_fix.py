#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "scripts" / "room_engine_v5.py"
MODEL = ROOT / "scripts" / "room_private_model.py"


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
        'def _allen_voice_engages(key, rank):\n',
        'def _direct_entity_question(event, entity):\n'
        '    """Return True only for a direct AI-to-AI question addressed to entity."""\n'
        '    if not isinstance(event, dict) or entity not in _AI_ORDER:\n'
        '        return False\n'
        '    speaker = str(event.get("speaker") or "").lower()\n'
        '    if speaker not in _AI_ORDER or speaker == entity:\n'
        '        return False\n'
        '    cognition = event.get("cognition") if isinstance(event.get("cognition"), dict) else {}\n'
        '    if str(cognition.get("target") or "").lower() != entity:\n'
        '        return False\n'
        '    return str(event.get("text") or "").rstrip().endswith("?")\n\n\n'
        'def _allen_voice_engages(key, rank):\n',
        "direct entity question detector",
    )

    replace_once(
        ENGINE,
        '        prior_same_beat = _core.prior_expression_messages(node) if role == "expression" else []\n'
        '        allen_latest = bool(\n',
        '        prior_same_beat = _core.prior_expression_messages(node) if role == "expression" else []\n'
        '        newest_same_beat = prior_same_beat[-1] if prior_same_beat and isinstance(prior_same_beat[-1], dict) else None\n'
        '        question_event = None\n'
        '        if role == "expression":\n'
        '            if _direct_entity_question(newest_same_beat, entity):\n'
        '                question_event = newest_same_beat\n'
        '            elif _direct_entity_question(latest, entity):\n'
        '                question_event = latest\n'
        '        question_reply = bool(question_event)\n'
        '        allen_latest = bool(\n',
        "capture direct question obligation",
    )

    replace_once(
        ENGINE,
        '        routed_allen_reply = primary_allen_reply or secondary_allen_reply or late_allen_reply\n'
        '    except Exception:\n'
        '        routed_allen_reply = False\n',
        '        routed_allen_reply = primary_allen_reply or secondary_allen_reply or late_allen_reply\n'
        '    except Exception:\n'
        '        question_reply = False\n'
        '        question_event = None\n'
        '        routed_allen_reply = False\n',
        "safe question fallback",
    )

    replace_once(
        ENGINE,
        '    if not routed_allen_reply:\n'
        '        # Core expression generation already makes the newest same-beat\n',
        '    if question_reply:\n'
        '        asker = str(question_event.get("speaker") or "").lower()\n'
        '        question_bus = copy.deepcopy(bus_data)\n'
        '        question_source = _core.rp(question_bus, entity, role)\n'
        '        question_base = question_source.get("private") if isinstance(question_source.get("private"), dict) else {}\n'
        '        question_base["event"] = copy.deepcopy(question_event)\n'
        '        question_base["partner"] = asker\n'
        '        question_context = list(question_base.get("context") or [])\n'
        '        if not question_context or question_context[-1] != question_event:\n'
        '            question_context.append(copy.deepcopy(question_event))\n'
        '        question_base["context"] = question_context[-8:]\n'
        '        try:\n'
        '            rel = _core.minds()["entities"][entity]["people"][asker]\n'
        '            question_base["relationship"] = {\n'
        '                k: rel.get(k) for k in (\n'
        '                    "exposure", "direct_familiarity", "trust", "predictability",\n'
        '                    "reciprocity", "warmth", "respect", "disclosure_depth", "tension"\n'
        '                )\n'
        '            }\n'
        '        except Exception:\n'
        '            pass\n'
        '        thought = ((question_bus.get("recurrent", {}).get(entity, {}) or {}).get("thought", {}) or {})\n'
        '        thought_private = thought.get("private") if isinstance(thought.get("private"), dict) else {}\n'
        '        deliberation = thought_private.get("deliberation") if isinstance(thought_private.get("deliberation"), dict) else None\n'
        '        if isinstance(deliberation, dict):\n'
        '            deliberation["action"] = "ANSWER"\n'
        '            deliberation["preferred_partner"] = asker\n'
        '            deliberation["focus"] = str(question_event.get("text") or "")[:240]\n'
        '            deliberation["new_information_goal"] = ""\n'
        '            deliberation.pop("conversation_job", None)\n'
        '        original_job = _core.conversation_job\n'
        '        _core.conversation_job = lambda *_args, **_kwargs: ""\n'
        '        try:\n'
        '            result = _original_recurrent(node, key, question_bus)\n'
        '        finally:\n'
        '            _core.conversation_job = original_job\n'
        '        if isinstance(result, dict):\n'
        '            result = dict(result)\n'
        '            private = dict(result.get("private") or {})\n'
        '            expression = private.get("expression")\n'
        '            if isinstance(expression, dict):\n'
        '                expression = dict(expression)\n'
        '                expression["target"] = asker\n'
        '                expression["move"] = "answer"\n'
        '                private["expression"] = expression\n'
        '                result["private"] = private\n'
        '        return result\n\n'
        '    if not routed_allen_reply:\n'
        '        # Core expression generation already makes the newest same-beat\n',
        "route addressed questions before topic drift",
    )

    replace_once(
        MODEL,
        '            out["intent"] = intent\n'
        '    else:\n',
        '            out["intent"] = intent\n'
        '        event = out.get("event") if isinstance(out.get("event"), dict) else {}\n'
        '        event_target = _norm(event.get("target"))\n'
        '        event_speaker = _norm(event.get("speaker"))\n'
        '        direct_question = bool(\n'
        '            self_entity in PEOPLE\n'
        '            and event_speaker in PEOPLE\n'
        '            and event_speaker != self_entity\n'
        '            and event_target == self_entity\n'
        '            and str(event.get("text") or "").rstrip().endswith("?")\n'
        '        )\n'
        '        if direct_question:\n'
        '            out["answer_required"] = True\n'
        '            out.pop("angle", None)\n'
        '            out["partner"] = event_speaker\n'
        '            current_intent = out.get("intent") if isinstance(out.get("intent"), dict) else {}\n'
        '            current_intent["move"] = "ANSWER"\n'
        '            current_intent["aim"] = "Answer the question directly before adding anything else."\n'
        '            out["intent"] = current_intent\n'
        '    else:\n',
        "compact direct question requirement",
    )

    replace_once(
        MODEL,
        '            "not the subject matter. Respond to the newest spoken line when there is one. Do not quote, paraphrase, "\n'
        '            "or restate a point another speaker has already made; contribute different information. Never reveal "\n',
        '            "not the subject matter. Respond to the newest spoken line when there is one. If answer_required is true, "\n'
        '            "answer the question in event directly before adding anything else; do not change the subject, dodge it, "\n'
        '            "or substitute an unrelated question. If you do not know, say so plainly. Do not quote, paraphrase, "\n'
        '            "or restate a point another speaker has already made; contribute different information. Never reveal "\n',
        "expression answer-required instruction",
    )

    replace_once(
        MODEL,
        '        if not isinstance(obj.get("semantic_terms"), list):\n'
        '            raise ValueError("missing_semantic_terms")\n'
        '    elif role == "thought":\n',
        '        if not isinstance(obj.get("semantic_terms"), list):\n'
        '            raise ValueError("missing_semantic_terms")\n'
        '        if compact.get("answer_required") is True:\n'
        '            event = compact.get("event") if isinstance(compact.get("event"), dict) else {}\n'
        '            asker = _norm(event.get("speaker"))\n'
        '            if str(obj.get("move") or "").lower() != "answer":\n'
        '                raise ValueError("question_not_answered")\n'
        '            if _norm(obj.get("target")) != asker:\n'
        '                raise ValueError("question_wrong_target")\n'
        '    elif role == "thought":\n',
        "validate direct answer move and target",
    )

    print("Entity question-answering repair applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
