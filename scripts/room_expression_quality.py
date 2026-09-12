from __future__ import annotations

"""Expression-quality wrapper with process-attractor retirement."""

import room_topic_bounded as _bounded_topic
import room_expression_quality_legacy as _legacy

PROCESS_TERMS = {
    "ground", "grounded", "grounding",
    "clarify", "clarifies", "clarified", "clarifying", "clarification", "clarifications", "clarity",
}

_bounded_topic._TOPIC_NOISE.update(PROCESS_TERMS)

for _name, _value in vars(_legacy).items():
    if not _name.startswith("__"):
        globals()[_name] = _value
