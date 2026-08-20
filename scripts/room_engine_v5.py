#!/usr/bin/env python3
from __future__ import annotations

"""Compatibility wrapper that makes Allen a real conversational participant.

The preserved core engine still has exactly four autonomous generators. This
wrapper changes participant-facing semantics only: Allen may be recognized as a
recent speaker/target, and the first autonomous speaker after an Allen turn gets
a real adjacency response opportunity. Iteration, indexing, node ownership, and
generation remain Sarah/Mara/Owen/Jules only.
"""

import copy
import os
import re

import room_private_model as _private_model

# Structured model output must be allowed to refer directly to Allen.
if "allen" not in _private_model.PEOPLE:
    _private_model.PEOPLE = [*_private_model.PEOPLE, "allen"]

import room_engine_v5_core as _core


class _ParticipantAwareOrder(tuple):
    """Iterate over four generators; treat Allen as a legal interlocutor."""

    def __contains__(self, item):
        return str(item or "").lower() == "allen" or super().__contains__(item)


_AI_ORDER = tuple(_core.ORDER)
ORDER = _ParticipantAwareOrder(_AI_ORDER)
PARTICIPANTS = _AI_ORDER + ("allen",)
_core.ORDER = ORDER

_ALLEN_RELATIONSHIP = {
    "exposure": 0.18,
    "direct_familiarity": 0.10,
    "trust": 0.10,
    "predictability": 0.10,
    "reciprocity": 0.10,
    "warmth": 0.10,
    "respect": 0.12,
    "disclosure_depth": 0.0,
    "tension": 0.0,
}


def _with_allen_relationship(mind):
    entities = (mind or {}).get("entities") or {}
    for entity in _AI_ORDER:
        state = entities.get(entity)
        if not isinstance(state, dict):
            continue
        people = state.setdefault("people", {})
        people.setdefault("allen", dict(_ALLEN_RELATIONSHIP))
    return mind


_original_fresh_minds = _core.fresh_minds
_original_minds = _core.minds


def fresh_minds():
    return _with_allen_relationship(_original_fresh_minds())


def minds():
    return _with_allen_relationship(_original_minds())


_core.fresh_minds = fresh_minds
_core.minds = minds

# A participant interruption is an adjacency event, not evidence that the
# ongoing topic has collapsed. Otherwise a repetitive room context can cause the
# first expression after Allen to discard Allen's turn and bridge elsewhere.
_original_context_collapsed = _core.context_collapsed


def _participant_context_collapsed(context):
    recent = list(context or [])
    if recent and isinstance(recent[-1], dict) and recent[-1].get("speaker") == "allen":
        return False
    return _original_context_collapsed(context)


_core.context_collapsed = _participant_context_collapsed

# The expression phase is sequential and ROOM_EXPRESSION_RANK=0 is the first AI
# voice after the latest public event. Give exactly that voice a response
# obligation when Allen is the latest speaker. The language remains model-made;
# this wrapper changes routing/intent only. Ranks 1-3 remain unconstrained.
_original_recurrent = _core.recurrent


def _participant_recurrent(node, key, bus_data):
    try:
        entity, _local, role, _tasks = _core.ni(node)
        rank = int(os.environ.get("ROOM_EXPRESSION_RANK", str(ORDER.index(entity))))
        source = _core.rp(bus_data, entity, role) if role == "expression" else None
        base = (source or {}).get("private") or {}
        latest = base.get("event") if isinstance(base.get("event"), dict) else None
        direct_allen_reply = bool(
            role == "expression"
            and rank == 0
            and base.get("partner") == "allen"
            and latest
            and latest.get("speaker") == "allen"
        )
    except Exception:
        direct_allen_reply = False
        entity = None

    if not direct_allen_reply:
        return _original_recurrent(node, key, bus_data)

    routed_bus = copy.deepcopy(bus_data)
    thought = ((routed_bus.get("recurrent", {}).get(entity, {}) or {}).get("thought", {}) or {})
    thought_private = thought.get("private") if isinstance(thought.get("private"), dict) else {}
    deliberation = thought_private.get("deliberation") if isinstance(thought_private.get("deliberation"), dict) else None
    if isinstance(deliberation, dict):
        deliberation["action"] = "ANSWER"
        deliberation["preferred_partner"] = "allen"
        deliberation["new_information_goal"] = ""
        deliberation.pop("conversation_job", None)

    # Suppress the ordinary per-voice distinct-contribution job for this single
    # adjacency response. The core still builds all four expressions normally.
    original_job = _core.conversation_job
    _core.conversation_job = lambda *_args, **_kwargs: ""
    try:
        result = _original_recurrent(node, key, routed_bus)
    finally:
        _core.conversation_job = original_job

    if isinstance(result, dict):
        result = dict(result)
        private = dict(result.get("private") or {})
        expression = private.get("expression")
        if isinstance(expression, dict):
            expression = dict(expression)
            expression["target"] = "allen"
            expression["move"] = "answer"
            # Live validation found a sharp hidden/surface mismatch: dozens of
            # replies targeted Allen in metadata while not one utterance used his
            # name. For the single adjacency reply, make the addressee audible.
            # Preserve model wording when it already names Allen.
            utterance = str(expression.get("utterance") or "").strip()
            if utterance and not re.search(r"\ballen\b", utterance, re.I):
                expression["utterance"] = f"Allen, {utterance}"
            private["expression"] = expression
            result["private"] = private
    return result


_core.recurrent = _participant_recurrent

# Re-export the preserved engine API. Functions remain bound to the core module,
# where ORDER/minds/fresh_minds/recurrent above have already been patched.
for _name in dir(_core):
    if _name.startswith("__") or _name in globals():
        continue
    globals()[_name] = getattr(_core, _name)

# Keep the wrapper's participant-aware values visible to importers such as
# room_private_commit.py.
globals()["ORDER"] = ORDER
globals()["PARTICIPANTS"] = PARTICIPANTS
globals()["fresh_minds"] = fresh_minds
globals()["minds"] = minds
globals()["recurrent"] = _participant_recurrent


def main():
    # room_private_commit.py replaces `room_engine_v5.commit` at runtime. The
    # preserved core's main() resolves globals in the core module, so forward
    # that override before dispatching the command.
    _core.commit = globals().get("commit", _core.commit)
    return _core.main()


if __name__ == "__main__":
    main()
