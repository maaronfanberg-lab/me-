# Endogenous Room multi-turn failure analysis (real Llama 3.2 3B)

## Previous 6-beat baseline (private cognition disabled)

[Actions run 41961135286](https://github.com/maaronfanberg-lab/me-/actions/runs/41961135286)

Six proposed, validated public turns; no silent beats; 24 model calls; 262.48 seconds. The dialogue migrated from an actual question about checking two cups marked 200 mL into generic talk about how people conceptualize measurement. Human-like development was not demonstrated.

## Real 6-beat retest (individual private cognition enabled)

[Actions run 41961973689](https://github.com/maaronfanberg-lab/me-/actions/runs/41961973689)

Six public speech selections, no silent beats, 31 model calls, 577.96 seconds; two model-generated private goals were accepted and four private belief revisions were committed. These are positive *internal-state* results, but the actual conversation still failed in three important ways:

1. One complete sentence about "context ... different scales we're operating on" was repeated almost verbatim on beats 2, 4, and 5. Model self-endorsement approved it each time. **A second internal decision alone does not ensure conversational freshness.**
2. A participant asserted that Mara's "confidence level has dropped ... after reconsidering her private hypothesis", despite lacking access to her hidden state. It was generated from speculation, not a witnessed fact. The result was incorrectly admitted as a public statement.
3. CPU usage and latency increased substantially. One extra private-cognition stage adds genuine opportunity for self-development but is **not free**. This workload cannot be treated as production-ready just because it passed syntax tests.

## Corrective changes implemented after this failure

- `room_endogenous_public_hygiene.py` rejects exact/near-verbatim copies and confident claims about another character's private cognitive state. It is a **negative publication gate** only. It never invents speech, rotates speakers, proposes topics, imposes novelty quotas, or orders a character to disagree. Both the volunteer selector and the transaction boundary enforce it.
- `room_endogenous_research_delivery.py` provides a crash-recoverable and idempotent *research-only* feed consumer. A simulated crash after writing the feed but before acknowledging delivery is handled by an identical-ID replay. There is **no** live production feed integration.
- `room_endogenous_behaviour_gate.py` separates engineering CI from observed behavior. A model run with duplicated utterances, unauthorized private-state assertions, non-specific responses to a testable question, or excessive time does not get a passing *behavioral* mark.
- Failed and timed-out inference attempts now count toward resource accounting, avoiding falsely low CPU-call totals.
- The synthetic, unit and integration tests are [green at the latest tested implementation](https://github.com/maaronfanberg-lab/me-/actions/runs/41964165092), totaling **133 research-specific checks**. These prove defined invariants on test cases; they do not prove unconstrained social intelligence.

## Gates still open

Long-form social quality with several characters, holdout scenarios and blind comparison; bounded practical model cost; Git-level atomic publication and rollback with the **actual** Room workflow; no hidden-state guesses under adversarial conversations. The experimental research publisher is deliberately isolated from the real `room/feed.json` and `room/live.json`. The live Room is unchanged.

**Do not deploy** solely on the strength of a green research unit-test suite. The final quality check requires independent real-model evidence and an operational release decision.
