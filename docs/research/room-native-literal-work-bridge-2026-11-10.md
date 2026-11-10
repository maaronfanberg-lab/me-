# Room action-to-work bridge: targeted operational repair

Date: 2026-11-10. Scope: native Concordia agent action to verified Room-life referee.

## 1. Observed problem

At live cycle 61,199, `room/state.json` showed native publication succeeding on that beat but `independent_life` remained at six completed tasks and no active task. Recent `room/feed.json` entries include explicit agent descriptions such as "I quietly organize my bookshelf" and "I inspect the notebook" while world object counters remained at two bookshelf observations and four notebook written pages. Across earlier hourly inspections the Room experienced long silent intervals. This patch **does not attempt to fix silence or general conversation quality**.

## 2. Foundational evidence

Concordia's Game Master pattern separates an agent's *proposed action* from the environment's *resolved consequence*. See Google DeepMind Concordia overview, https://github.com/google-deepmind/concordia (retrieved 2026-11-10). Event-sourcing principles likewise distinguish state-changing accepted events from unverified narration: Martin Fowler, Event Sourcing (2005), https://martinfowler.com/eaaDev/EventSourcing.html .

## 3. Current evidence

Concordia's environment/engine documentation describes `resolve` as finalizing a putative action into the world state: https://github.com/google-deepmind/concordia/blob/main/concordia/environment/README.md (retrieved 2026-11-10). Concordia 2.3.0 in February 2026 emphasizes JSON action parsing. Source: https://github.com/google-deepmind/concordia/blob/main/CHANGELOG.md (retrieved 2026-11-10). We preserve strict JSON scheduler controls and prefer explicitly structured `work`.

## 4. Natural behavior evidence

A direct present-tense physical action ("I inspect the notebook") is materially different from a proposed, hypothetical, recalled, or promised action ("I might inspect...", "I inspected...", "I'll inspect..."). This patch does not infer mental states or introduce dialogue scripts. The assumption that literal present-tense action is a valid request is restricted to the Room's simple existing affordances, not generalized human speech.

## 5. Mechanism

Before: `room_life.advance` accepted only optional `work: {verb,object}` inside otherwise valid native JSON. An agent could choose and narrate a recognizable action without the optional work field; no task began, so there was nothing to complete and nothing new for other characters to witness.

After: if, and only if, the control JSON is valid and its `work` field **absent**, parse a very small set of *complete*, literal, present-tense, first-person action sentences. This creates a referee-validated **work_started** request, not a completed outcome. Completion still requires ordinary elapsed cycles, verified affordances, and a vacant character task slot. No words are put into any character's mouth.

## 6. Competing explanations

Stagnation may also arise from repetitive model sampling, attention masks, invalid JSON controls, memory priming, model size, speech filtering, or insufficient goal diversity. This bridge specifically targets missing causal state updates, not those unrelated mechanisms.

## 7. Replication and limitations

The rule can miss natural-language variants (false negatives), and could interpret an unambiguous present action as intending to work when the agent omitted the optional explicit work command. We deliberately reject compound actions, future/hypothetical claims, other-speaker prefixes, incompatible affordances, and malformed controls. We do not assert that completion counters measure human-like autonomy.

## 8. Context-transfer check

A strict grammar is suitable only for the Room's existing small set of toy physical affordances. It is not a general natural-language understanding system, psychological model, or social-response policy. It preserves independently chosen actions and does not add recommended responses to Allen.

## 9. Implementation

`scripts/room_life.py` adds `_literal_work_from_action` and invokes it as a fallback only for missing `work` fields. `scripts/test_room_life.py` checks valid action acceptance, deferred completion, and negative cases. Existing explicit `work` semantics are unchanged. This patch does not touch scheduler configuration, checkpoint, user history, secrets, or GitHub runners.

## 10. Post-change validation

Pre-change live baseline: cycle 61,199, zero active tasks, six completed tasks; bookshelf observations 2, notebook written pages 4. Before merge require the native Concordia integration workflow to pass all tests and a reviewed diff. After merge compare at least 50 new live cycles for newly started/completed validated tasks, verified world events, and second-order responses in dialogue. Watch for a spike in mechanical, repetitive actions, unexpected task starts, or continued absence of outcomes; revert if adverse. Production verification pending; this research note does **not** claim a live fix.
