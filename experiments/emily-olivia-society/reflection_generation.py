#!/usr/bin/env python3
"""Runtime reflection-output adapter for the local Stanford + BitNet path.

Stanford HCI asks for JSON reflection output. The small local Falcon model can
instead return a perfectly usable natural-language insight. Treating every
non-JSON answer as empty causes reflection to disappear even though the model
answered the research-derived prompt.

This module changes only parsing. It never authors, rewrites, or substitutes a
reflection. JSON output remains preferred; raw model text is accepted only when
it passes the same reflection-hygiene boundary used for durable memory.
"""
from __future__ import annotations

import re

from reflection_hygiene import is_clean_reflection_text

_INSTALLED_MARKER = "COMMUNITY_NATURAL_REFLECTION_V1"
_BULLET_PREFIX = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s+")


def _candidate_texts(response: object, memory_module, reflection_count: int) -> list[str]:
    if not isinstance(response, str):
        return []
    raw = response.strip()
    if not raw:
        return []
    if raw.startswith("GENERATION ERROR:"):
        raise RuntimeError(raw)

    parsed = memory_module.extract_first_json_dict(raw)
    candidates: list[object] = []
    if isinstance(parsed, dict):
        reflection = parsed.get("reflection")
        candidates = reflection if isinstance(reflection, list) else [reflection]
    else:
        # Accept only the model's own declarative prose. Structured-looking raw
        # output stays rejected so malformed JSON cannot become autobiography.
        if raw.startswith(("```", "{", "[", "<")):
            return []
        lines = [
            _BULLET_PREFIX.sub("", line).strip()
            for line in raw.splitlines()
            if line.strip()
        ]
        clean_lines = [line for line in lines if is_clean_reflection_text(line)]
        candidates = clean_lines if clean_lines else [raw]

    cleaned: list[str] = []
    for item in candidates:
        text = ""
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            for key in ("insight", "reflection", "thought", "sentence"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    text = value.strip()
                    break
        if not is_clean_reflection_text(text):
            continue
        cleaned.append(text[:1000])
        if len(cleaned) >= max(1, int(reflection_count)):
            break
    return cleaned


def install_natural_reflection_parser() -> None:
    """Patch Stanford's reflection parser in memory for this process only."""
    import genagents.modules.memory_stream as memory_module

    if getattr(memory_module, _INSTALLED_MARKER, False):
        return

    def run_gpt_generate_reflection(
        records,
        anchor,
        reflection_count,
        prompt_version="1",
        gpt_version="GPT4o",
        verbose=False,
    ):
        records_str = ""
        for count, record in enumerate(records):
            records_str += f"Item {count + 1}:\n{record}\n"
        prompt_input = [records_str, reflection_count, anchor]
        fail_safe: list[str] = []
        if reflection_count > 1:
            prompt_lib_file = (
                f"{memory_module.LLM_PROMPT_DIR}/generative_agent/"
                "memory_stream/reflection/batch_v1.txt"
            )
        else:
            prompt_lib_file = (
                f"{memory_module.LLM_PROMPT_DIR}/generative_agent/"
                "memory_stream/reflection/singular_v1.txt"
            )

        def clean_up(gpt_response, prompt=""):
            return _candidate_texts(
                gpt_response,
                memory_module,
                reflection_count,
            )

        output, prompt, prompt_input_out, fail_safe_out = memory_module.chat_safe_generate(
            prompt_input,
            prompt_lib_file,
            gpt_version,
            1,
            fail_safe,
            clean_up,
            verbose,
        )
        return output, [output, prompt, prompt_input_out, fail_safe_out]

    memory_module.run_gpt_generate_reflection = run_gpt_generate_reflection
    setattr(memory_module, _INSTALLED_MARKER, True)
