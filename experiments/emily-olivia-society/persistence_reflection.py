#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from community_cycle import load_agents, next_community_time_step
from reflection_hygiene import sanitize_memory_stream

HERE = Path(__file__).resolve().parent
REPLAY_DIR = HERE / "replay"
_EMPTY_EMBEDDING_ERROR = "Input text must be a non-empty string."
_MAX_REFLECTION_ATTEMPTS = 8


def node_counts(brain) -> dict[str, int]:
    counts = {"observation": 0, "reflection": 0, "total": 0}
    for node in brain.memory_stream.seq_nodes:
        counts["total"] += 1
        if node.node_type in counts:
            counts[node.node_type] += 1
    return counts


def relevant_memories(agent, other_name: str, time_step: int, n_count: int = 12) -> list[str]:
    query = f"Interaction and relationship with {other_name}"
    retrieved = agent.brain.memory_stream.retrieve(
        [query],
        time_step=time_step,
        n_count=n_count,
    )
    return [node.content for node in retrieved.get(query, [])]


def _run_reflection_pass(agent, anchor: str, time_step: int, retrieval_count: int) -> None:
    """Run one Stanford reflection pass and discard malformed generated nodes."""
    try:
        agent.brain.memory_stream.reflect(
            anchor=anchor,
            reflection_count=3,
            retrieval_count=retrieval_count,
            time_step=time_step,
        )
    except ValueError as exc:
        if str(exc) != _EMPTY_EMBEDDING_ERROR:
            raise
    finally:
        sanitize_memory_stream(agent.brain.memory_stream)


def reflect_and_verify(agent, other_name: str, time_step: int) -> dict:
    sanitize_memory_stream(agent.brain.memory_stream)
    before = node_counts(agent.brain)
    relevant_before = relevant_memories(agent, other_name, time_step)

    if not relevant_before:
        return {
            "agent": agent.name,
            "status": "skipped",
            "reason": "no_prior_memories",
            "time_step": time_step,
            "before": before,
            "retrieved_before": [],
        }

    anchor = f"{agent.name}'s higher-level understanding of interactions with {other_name}"
    retrieval_count = min(12, max(1, before["total"]))

    # The 1B local model is stochastic and can occasionally return malformed or
    # question-shaped reflection output. Resample the same Stanford request at
    # the same logical timestep; hygiene still rejects every bad node and no
    # authored fallback reflection is ever inserted.
    for _attempt in range(_MAX_REFLECTION_ATTEMPTS):
        _run_reflection_pass(
            agent,
            anchor,
            time_step=time_step,
            retrieval_count=retrieval_count,
        )
        if node_counts(agent.brain)["reflection"] > before["reflection"]:
            break
    else:
        raise RuntimeError(
            f"Stanford reflection produced no clean persisted insight for {agent.name} after "
            f"{_MAX_REFLECTION_ATTEMPTS} same-anchor attempts."
        )

    agent.brain.save(str(agent.workspace))

    after_save = node_counts(agent.brain)
    new_reflections = [
        node.content
        for node in agent.brain.memory_stream.seq_nodes
        if node.node_type == "reflection"
    ][before["reflection"] :]

    from genagents.genagents import GenerativeAgent

    reloaded = GenerativeAgent(str(agent.workspace))
    sanitize_memory_stream(reloaded.memory_stream)
    after_reload = node_counts(reloaded)
    relevant_after_reload = relevant_memories(
        type("ReloadedAgent", (), {"brain": reloaded})(),
        other_name,
        time_step,
    )

    if after_reload["reflection"] < after_save["reflection"]:
        raise RuntimeError(f"Reflection persistence verification failed for {agent.name}.")
    if not new_reflections or not all(str(item).strip() for item in new_reflections):
        raise RuntimeError(f"Clean reflection verification failed for {agent.name}.")

    return {
        "agent": agent.name,
        "status": "reflected",
        "time_step": time_step,
        "anchor": anchor,
        "before": before,
        "after_save": after_save,
        "after_reload": after_reload,
        "retrieved_before": relevant_before,
        "new_reflections": new_reflections,
        "retrieved_after_reload": relevant_after_reload,
        "persisted": True,
    }


def run_layer6() -> dict:
    agents = load_agents()
    names = {agent.name for agent in agents}
    if names != {"Emily", "Olivia"}:
        raise RuntimeError("Layer 6 expects exactly Emily and Olivia.")

    base_time_step = next_community_time_step(agents)
    reports = []
    for offset, agent in enumerate(agents):
        other = next(a for a in agents if a.agent_id != agent.agent_id)
        reports.append(
            reflect_and_verify(
                agent,
                other.name,
                time_step=base_time_step + offset,
            )
        )

    result = {
        "mode": "layer6_persistence_and_reflection",
        "autonomous_loop": False,
        "start_time_step": base_time_step,
        "agents": reports,
    }

    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    (REPLAY_DIR / "layer6_reflection.json").write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify Emily and Olivia retrieve prior memories, reflect, persist, and reload them."
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Explicitly permit one reflection/persistence pass for each agent, then stop.",
    )
    args = parser.parse_args()

    if not args.run:
        raise SystemExit(
            "Refusing to start automatically. Use --run for one bounded Layer 6 reflection pass."
        )

    print(json.dumps(run_layer6(), indent=2))


if __name__ == "__main__":
    main()
