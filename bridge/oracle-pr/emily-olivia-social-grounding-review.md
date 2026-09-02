# Read-only engineering review task

Do not modify runtime code. Do not alter The Room. Do not dispatch or create Community runs. This branch exists only to provide review context.

Review the autonomous two-agent dialogue control design below.

- Live cognitive chain: observe → remember → retrieve → reflect → plan/react → act.
- Original Stanford Generative Agents source is pinned at `fe05a71d3e4ed7d10bf68aa4eda6dd995ec070f4`.
- Previous nested retry layers could multiply into hundreds of completions for one spoken turn, causing apparent stalls. Those multipliers were reduced to single-pass.
- The social refractory wrapper now allows exactly two samples at one layer: initial sample plus one retry. If both structurally valid samples are soft attractors, it publishes the first valid sample instead of stalling.
- Every other boundary, attractor, and session retry layer remains single-pass.
- Hard identity contradictions and impossible self-conversation claims must never publish.
- A second observed failure is unsupported shared-world premises, such as an invented event, becoming persistent because later memory retrieval treats dialogue observations as evidence.
- No canned dialogue and no phrase/topic-specific replacement rules are allowed.

Please provide a review comment addressing:

1. Whether the two-sample single-layer refractory design preserves liveness.
2. Any remaining hidden multiplicative retry or dead-turn path.
3. The best architectural home for soft social-attractor rejection.
4. A principled provenance scheme so speech-derived claims remain claims and do not silently become world facts during memory retrieval.
5. Concrete falsification tests for throughput, identity integrity, grounding, and conversational variety.

Analysis only. Do not implement changes.