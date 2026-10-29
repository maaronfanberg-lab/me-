# Room 1B vs 3B capacity trial: research gate

**Status:** shadow-only, never publish tests as Room speech. Do not automatically promote a larger model.

## Observed problem

On 2026-10-28 the published Llama 3.2 1B Room displayed repeated questions, one-word scaffolds and disconnected replies. The actual 1B production-wrapper A/B in Room PR #336 (run 40789717923) copied full previous statements in three of four source-retained paired cases. The live transcript after the no-bid selection fix similarly repeated multi-sentence species-evolution questions. Exact source-linked examples can be recovered in room/feed.json; this report avoids assuming more parameters fix behavior.

## Research question

Does a locally hosted quantized Llama 3.2 3B Instruct model, under the **same Room production prompt, context, seed and decoder behavior**, produce meaningfully better response actions and fewer whole-turn copies than the existing Llama 3.2 1B Instruct model?

## Ten-level research gate

1. Observed issue: saved 1B raw outputs and current public feed; structural failure and semantic discontinuity.
2. Foundation: conditional relevance of adjacent turns (Sacks, Schegloff & Jefferson 1974), collaborative grounding (Clark & Wilkes-Gibbs 1986).
3. Contemporary technical evidence: Hugging Face publishes Llama 3.2 3B Instruct GGUF Q4_K_M, about 2.02 GB, materially larger than 1B. That availability is NOT an empirical result for this specific Room workload.
4. Natural behavior: human responses include repair, genuine disagreement, following details, and topic transitions. Evaluate actions, not lexical novelty.
5. Mechanism: increased model capacity might reduce failures to interpret densely structured persona + multi-agent context.
6. Alternatives: prompt length, stale state, hidden targets, wrong decoder, absent conversation-action integrity, and weak floor selection.
7. Replication limitations: four examples and a short chain are only pilot evidence; model variants may differ in speed, memory, quantization and stochastic generations.
8. Transfer: local Llama models, four-agent identity and GitHub Actions CPU are unusual; other chat benchmarks cannot certify success.
9. Mapping: isolated side-by-side model server trials via actual production wrapper, identical public fixtures/seeds and decoder. No main/model selection change in this PR.
10. Validation: capture utterances + timings, failed attempts, exact whole-action copies and short responses; manually judge specificity, grounded relevance, 5-turn continuation; consider performance and safety before any deployment.

## Decision rules

- A model qualifies for further canary only if it consistently provides specific, relevant responses and meaningful followups, rather than longer but disconnected output.
- A single positive example is insufficient. Compare at least four mixed examples, an actual multi-turn chain, and output quality vs latency.
- No changing participant personalities, forcing scripts, banning topics or assuming 3B is intrinsically better.
- Verify the model file origin, recorded SHA256 and runtime checksum; do not store model binaries in Git or expose secrets.
- Protect human-participant (Allen) messages and private memory; only public synthetic source fixtures used.

## Evidence URLs

- https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF
- https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF
- https://github.com/maaronfanberg-lab/me-/pull/336

## Outcome

Pending isolated experiment. No production model upgrade.
