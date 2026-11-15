#!/usr/bin/env python3
from __future__ import annotations

import room_private_commit as commit
import room_social_v5 as social


def message(speaker: str, text: str, terms: list[str], episode_id: str) -> dict:
    return {
        "speaker": speaker,
        "text": text,
        "cognition": {
            "topic_episode": episode_id,
            "topic_terms": terms,
        },
    }


def pathological_topic(cycle: int = 500) -> dict:
    topic = social.topic_template(cycle)
    topic["semantic_schema"] = 4
    topic["root"] = "books"
    topic["current_facet"] = "depth-37"
    topic["facets"] = [f"depth-{i}" for i in range(1, 38)]
    topic["visited_facets"] = list(topic["facets"])
    topic["branches"] = [
        {"label": "books", "parent": None, "depth": 0, "first_cycle": cycle - 40, "last_cycle": cycle, "hits": 40, "status": "open"}
    ]
    parent = "books"
    for depth in range(1, 38):
        label = f"depth-{depth}"
        topic["branches"].append({
            "label": label,
            "parent": parent,
            "depth": depth,
            "first_cycle": cycle - (38 - depth),
            "last_cycle": cycle,
            "hits": 2,
            "status": "open",
        })
        parent = label
    topic["branch_history"] = [f"depth-{i}" for i in range(1, 38)]
    topic["status"] = "active"
    return topic


def assert_flat(topic: dict) -> None:
    branches = list(topic.get("branches") or [])
    depths = [int(branch.get("depth", 0)) for branch in branches]
    assert max(depths or [0]) <= 1, f"runaway topic depth survived replacement: {max(depths)}"
    assert len(branches) <= 9, branches
    root = topic.get("root")
    for branch in branches:
        if int(branch.get("depth", 0)) == 1:
            assert branch.get("parent") == root, f"non-root facet is not a sibling under root: {branch}"
    assert len(topic.get("facets", [])) <= 8, topic.get("facets")
    assert len(topic.get("visited_facets", [])) <= 8, topic.get("visited_facets")
    assert len(topic.get("branch_history", [])) <= 8, topic.get("branch_history")
    assert int(topic.get("semantic_schema", 0)) == 5, topic.get("semantic_schema")


def main() -> None:
    topic = pathological_topic()
    episode = topic["id"]
    history = [
        message("sarah", "I keep thinking about the ending of this book.", ["books", "ending"], episode),
        message("mara", "The ending changes how I see the main character.", ["books", "ending", "character"], episode),
        message("owen", "The evidence in the final chapter matters more than the reputation of the novel.", ["books", "final chapter", "evidence"], episode),
    ]
    bounded = social.update_topic(topic, history, 501)
    assert_flat(bounded)
    assert bounded.get("bridge_pending") is True, "runaway migration lost its one-time escape signal"
    assert social.should_shift_topic(bounded), "runaway migration is not scheduled to leave the poisoned episode"

    replacement = social.new_topic_from_terms(["astronomy", "moons", "orbits"], 502, bounded)
    assert replacement.get("bridge_pending") is False, "new episode inherited migration escape state"
    assert replacement.get("id") != bounded.get("id")
    assert_flat(replacement)

    old_id = bounded["id"]
    same_subject = message(
        "allen",
        "What did you think about the ending of that book?",
        ["books", "ending"],
        old_id,
    )
    stayed = social.update_topic(bounded, [*history, same_subject], 502)
    assert stayed.get("id") == old_id, "outside participant was treated as a topic reset despite staying on subject"

    outside_turn = message(
        "allen",
        "Let's talk about platypuses and why the males have venomous ankle spurs.",
        ["platypuses", "venomous ankle spurs"],
        old_id,
    )
    shifted = social.update_topic(bounded, [*history, outside_turn], 503)
    assert shifted.get("id") != old_id, "genuinely new outside-participant subject was swallowed by stale episode"
    assert shifted.get("root") == "platypuses", shifted
    assert shifted.get("bridge_pending") is False
    assert_flat(shifted)

    # Twenty successive AI-originated ideas must remain sibling facets rather than
    # reconstructing the old child-of-child ladder.
    rolling = shifted
    ideas = [
        "migration", "wetlands", "electroreception", "eggs", "burrows",
        "rivers", "taxonomy", "evolution", "swimming", "foraging",
        "mammals", "venom", "habitat", "conservation", "nocturnal",
        "webbed feet", "temperature", "predators", "streams", "adaptation",
    ]
    for offset, idea in enumerate(ideas, 1):
        eid = rolling["id"]
        turn = message("jules", f"A new angle is {idea}.", [rolling["root"], idea], eid)
        rolling = social.update_topic(rolling, [turn], 503 + offset)
        assert_flat(rolling)

    expr = {"semantic_terms": ["platypuses", "public-interest", "books"]}
    spoken = "Platypuses are mammals, and the males can carry venom in ankle spurs."
    terms = commit.clean_terms(expr, {"root": "books", "current_facet": "classics"}, spoken)
    assert "platypuses" in terms, terms
    assert "public-interest" not in terms, terms
    assert "books" not in terms, "stale topic term was re-declared despite not appearing in the spoken line"

    print("ROOM BOUNDED TOPIC SIM: GREEN")


if __name__ == "__main__":
    main()
