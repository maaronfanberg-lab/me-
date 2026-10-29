# Room: output-format hypothesis (speech first, structure optional)

Status: shadow-only, no production mutation, no dialogue publication.

## Source evidence

The production Llama 3.2 1B single-pass model must emit JSON with `decision`, `move`, `target`, `semantic_terms`, `utterance`. Actual 1B pilot tests show literal echo, generic scaffold and invented context. The 3B trial failed 3/4 reply validity within timeout; Qwen2.5 1.5B gave 4/4 responses but the five-turn chain drifted. Lean 1B prompt improved one ecosystem reply but also hallucinated and duplicated. The active Room repeatedly produces short labels and unfinished fragments.

## Hypothesis

A 1B instruction model may generate more responsive speech when asked for a single conversational turn via its native chat template rather than a large JSON schema. This is a competing hypothesis to prompt/source-memory limitation and must be compared on exact saved public Room turns. Even if shadow quality improves, safely returning such output to the Room would need an explicit deterministic metadata/integrity mapping, not simply disabling existing validation.

## Ten-level research gate

1. Observed public failures and saved production-wrapper A/B utterances.
2. Foundation: human next-turn relevance, repair and accountable speaker turns.
3. Model-format evidence: the current llama.cpp runtime supports chat completions; compare that surface rather than assuming structured JSON improves speech.
4. Natural target: concrete answers, independent stance, valid topic shifts, no narration of internal roles.
5. Mechanism: shift token budget from schema to content; speaker identity stays in system context.
6. Alternatives: shorter prompt, fewer memories, different decoder temperature, source retention, model family capacity.
7. Limits: speech-format and prompt change together, so improvement cannot be attributed to one; one pilot cannot generalize.
8. Transfer: natural conversation is not just a line of fluent text; final speech still requires provenance, self-identity, coherent recipient and cross-turn validation.
9. Implementation: shadow script runs chat/completions on pinned local Llama 1B with same public sources, character identity and deterministic seeds. No production codepath or persistent state changed.
10. Validation: 4 source-linked replies and 6-turn continuation; record full speech, latency, identity leakage, exact copies and whether followup addresses actual stance. Reject if disconnected, unsafe, role-leaking, or poor latency; if promising, a separate PR must integrate and run complete publication regression and live canary.

## Safety

Do not treat fluent single outputs as genuine sustained dialogue. Do not bypass strict live publication safety gates, invert source and speaker, invent Allen participation or overwrite memories. A passing workflow only means the experiment completed, not that the architecture is deployable.

Outcome: pending direct text comparison.
