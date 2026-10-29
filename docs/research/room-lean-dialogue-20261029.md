# Lean source-grounded dialogue: 1B architecture ablation

Status: isolated comparison only, no publication, no live deployment.

## Observations

The 2026-10-28 Room deployed a 1B local transformer with a long persona, group recall, structured social fields and verbose prompt. Logs show repeated questions and generic meta-talk. A 1B-versus-3B capacity trial on public source-linked fixtures showed the 1B answered 4/4 but generated an off-topic 5-turn chain, whereas the 3B failed to produce a valid expression in 3/4 cases within the 70-second per-case bound and failed to continue a chain. Simply increasing model capacity is not an operational fix in this CPU setting.

## Research question

Is task/context overload contributing to 1B failure, and can a shorter action-oriented prompt and compressed per-character profile produce more responsive speech while preserving agency and distinctive voice?

## The 10-level gate

1. Observations: real public Room transcripts and comparable model trials with saved utterances.
2. Foundation: turn and sequence organization; an adjacent response displays an interpretation of the preceding action.
3. Current technical evidence: direct empirical 1B/3B runs in this exact workflow are more relevant than general model rankings.
4. Natural behavior: humans need not mimic prior wording; allow disagreement, clarification, short sincere responses and meaningful topic changes.
5. Mechanism: reduce instructions and noisy recalled context so a resource-limited 1B model can attend to a small number of particular public contributions.
6. Alternatives: generator capacity, temperature, random seeds, persona differences, semantic lack of memory and previously corrupted state.
7. Limits: shortened prompts can underfit personal history; ablation changes prompt and temperature simultaneously, so later factorial tests are required before causal attribution.
8. Context transfer: four longitudinal autonomous entities differ from ordinary human dyads; do not impose canned turns or forced topical persistence.
9. Implementation: isolated monkeypatch of model prompt, profile lens, old recalled group encounters and temperature cap .76, while production wrapper and output schema remain real.
10. Validation: same witnessed public source IDs as the baseline, same seed and model binary. Collect 4 replies and 5 generated turns; judge actual contextual response and specificity, not overlap alone. Re-run independent seeds if promising, then separately reintroduce memory and persona dimensions.

## Safety and non-goals

Do not treat source statements as facts or invent shared past; keep original authoring/memory unchanged. Never deploy this experiment itself. If characters become generic or no one develops concrete ideas, reject.

## Comparison

Baseline: docs/research/room-capacity-1b-20261029.json on the research/room-3b-capacity-20261029 branch. Lean trial writes docs/research/room-capacity-lean1b-20261029.json. Both contain public fixtures and machine-observed, not self-scored, generated replies.

Outcome: pending.
