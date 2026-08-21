from __future__ import annotations

import copy

import room_engine_v5_core as _core

_AUTONOMOUS = set(_core.ORDER)


def _ranked_prior_expression_messages(current_node: int) -> list[dict]:
    """Return completed same-beat expressions in the order they were spoken."""
    ranked: list[tuple[int, int, dict]] = []
    for path in _core.PARTS.glob("recurrent-*.json"):
        part = _core.load(path, {})
        if not isinstance(part, dict) or part.get("role") != "expression":
            continue
        try:
            node = int(part.get("node", -1))
        except Exception:
            node = -1
        if node == current_node:
            continue

        private = part.get("private") if isinstance(part.get("private"), dict) else {}
        expression = private.get("expression") if isinstance(private.get("expression"), dict) else {}
        text = str(expression.get("utterance") or "").strip()
        speaker = str(part.get("entity") or "").lower()
        if not text or speaker not in _AUTONOMOUS:
            continue

        intent = private.get("intent") if isinstance(private.get("intent"), dict) else {}
        try:
            rank = int(intent.get("generation_rank", 99))
        except Exception:
            rank = 99
        ranked.append((rank, node, {
            "speaker": speaker,
            "text": text,
            "cognition": {"target": expression.get("target")},
        }))

    ranked.sort(key=lambda row: (row[0], row[1]))
    return [message for _rank, _node, message in ranked]


# room_parts is cleared at the start of every beat, so generation_rank is the
# canonical chronology for the temporary expressions that exist here. Filename
# order is node topology, not conversational order.
_core.prior_expression_messages = _ranked_prior_expression_messages


def _reply_focus(message: dict) -> str:
    text = str((message or {}).get("text") or "").strip()
    terms = _core.toks(text)[:6]
    if terms:
        return " ".join(terms)
    return text[:140]


def _relationship(entity: str, partner: str) -> dict:
    try:
        rel = _core.minds()["entities"][entity]["people"][partner]
    except Exception:
        return {}
    return {
        key: rel.get(key)
        for key in (
            "exposure",
            "direct_familiarity",
            "trust",
            "predictability",
            "reciprocity",
            "warmth",
            "respect",
            "disclosure_depth",
            "tension",
        )
    }


def _fresh_reply_bus(bus_data: dict, entity: str, newest: dict) -> tuple[dict, str, bool]:
    partner = str((newest or {}).get("speaker") or "").lower()
    direct_question = bool(_core.isq(newest))
    refreshed = copy.deepcopy(bus_data)

    try:
        source = _core.rp(refreshed, entity, "expression")
        base = source.get("private") if isinstance(source.get("private"), dict) else {}
        base["partner"] = partner
        rel = _relationship(entity, partner)
        if rel:
            base["relationship"] = rel
    except Exception:
        pass

    thought = ((refreshed.get("recurrent", {}).get(entity, {}) or {}).get("thought", {}) or {})
    thought_private = thought.get("private") if isinstance(thought.get("private"), dict) else {}
    deliberation = thought_private.get("deliberation")
    if not isinstance(deliberation, dict):
        deliberation = {}
        thought_private["deliberation"] = deliberation

    # The old thought was formed before this same-beat turn existed. Preserve the
    # person's deeper state, but replace the stale conversational plan with one
    # anchored to what was actually just said.
    deliberation["preferred_partner"] = partner
    deliberation["action"] = "ANSWER" if direct_question else "DEEPEN"
    focus = _reply_focus(newest)
    if focus:
        deliberation["focus"] = focus
    else:
        deliberation.pop("focus", None)
    deliberation.pop("new_information_goal", None)
    deliberation.pop("conversation_job", None)
    deliberation.pop("shared_reference", None)
    deliberation.pop("unresolved_thread", None)

    return refreshed, partner, direct_question


def _align_result(result: object, partner: str, direct_question: bool):
    if not isinstance(result, dict):
        return result
    out = dict(result)
    private = dict(out.get("private") or {})
    expression = private.get("expression")
    if not isinstance(expression, dict):
        return result
    expression = dict(expression)
    expression["target"] = partner
    if direct_question:
        expression["move"] = "answer"
    private["expression"] = expression
    out["private"] = private
    return out


if not getattr(_core.recurrent, "_room_ai_adjacency", False):
    _original_recurrent = _core.recurrent

    def _adjacency_recurrent(node, key, bus_data):
        try:
            entity, _local, role, _tasks = _core.ni(node)
        except Exception:
            return _original_recurrent(node, key, bus_data)

        if role != "expression":
            return _original_recurrent(node, key, bus_data)

        prior = _core.prior_expression_messages(node)
        if not prior:
            return _original_recurrent(node, key, bus_data)

        newest = prior[-1] if isinstance(prior[-1], dict) else {}
        partner = str(newest.get("speaker") or "").lower()
        if partner not in _AUTONOMOUS or partner == entity:
            return _original_recurrent(node, key, bus_data)

        refreshed, partner, direct_question = _fresh_reply_bus(bus_data, entity, newest)
        result = _original_recurrent(node, key, refreshed)
        return _align_result(result, partner, direct_question)

    _adjacency_recurrent._room_ai_adjacency = True
    _core.recurrent = _adjacency_recurrent
