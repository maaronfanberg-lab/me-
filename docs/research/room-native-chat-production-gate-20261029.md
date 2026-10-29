# Room: speech-first local model architecture and live acceptance

**Status:** production candidate, initially held in draft PR #348 until actual local model and unmodified publication preflight checks pass. Emergency backend disable: GitHub repository variable `ROOM_CHAT_SPEECH_MODE_DISABLE=1`, followed by a controlled Room restart.

## Evidence and why this approach differs

The initial live structured-output Llama3.2 1B approach produced copied long questions, one-word internal role labels and disconnected meta-conversation. Increasing to 3B on current CPU produced only 1/4 valid replies within 70s; Qwen2.5 1.5B was valid but frequently drifted; lean structured 1B also copied and wandered. A local model-format viability run in PR #347 used the **same quantized Llama3.2 1B GGUF and llama.cpp runtime** but its native `/v1/chat/completions` interface, two message roles, shorter transcript and no JSON schema. Four of four public-source replies were valid, 0 full-source copies, and a six-turn chain included recognizably developed discussion about convergent evolution, hypothetical photosynthetic organisms and their ecological implications. Ten model requests used about 25 seconds of inference on that isolated GitHub runner. These are human-inspected, small-sample observations; format, prompt and message-context changed together, not a controlled attribution.

## Main engineering mechanism

1. The *same* selected character retains the private Room identity, profile core identity and two established motives; no arbitrary characters or scripts.
2. The local model sees up to three witnessed public utterances and returns only its own text. Allen's accepted words remain available verbatim up to 700 characters. Sleeping characters are filtered from current presence.
3. The generation endpoint must be loopback HTTP to prevent sending private Room data to an unknown third-party model.
4. The speech adapter does not invent utterances. It derives provisional target, move and semantic terms solely for compatibility with the existing Room envelope, assigning speech itself as evidence rather than treating move labels as certified comprehension.
5. The selected-speaker preflight and final commit validators remain unchanged, including control-label hygiene, exact long-action copy quarantine, quality checks, addressed recipient resolution, topic state and memory provenance.
6. The older JSON-schema route remains available through a single repo-variable emergency disable switch; disabled mode must not alter the speech codepath.

## Research grounding and ten gates

1. Witnessed failure: real published speech loops and protocol scaffold.
2. Human conversation foundation: locally relevant next-turn action and repair, not forced repetition bans (Sacks, Schegloff, Jefferson 1974).
3. Current model evidence: the production-class same-model shadow trial is more informative than general benchmarks, but is a tiny sample.
4. Natural behavior: each character can engage, disagree, joke, ask or change topic, retaining own stance and relationships.
5. Mechanism: reduce structured-response burden, display real public turns in chat role context.
6. Alternatives: persona differences, prior state, decoder temperature, content selection and model-family size; the pilot does not isolate these.
7. Limits: a 1B model can still hallucinate, get theatrical, become hostile or change topics too quickly; long-term continuity is not assured.
8. Context transfer: fluent text must still satisfy real-world source, identity, privacy and durability rules.
9. Implementation: opt-in native chat model adapter in the existing expression slot; no changes to four-character floor or saving pipeline.
10. Validation: unit tests, actual model smoke against four public source fixtures with selected expression preflight, independent multi-turn chain. After canary, observe at least 30 consecutive new public turns and identify a grounded **five-turn** exchange with meaningful response, followup, and further development. Do not count exact echo, shared nouns, or one apparent answer. Keep rollback available.

## Rollback conditions

Disable and restart if any private text leaks, wrong speaker publishes, Allen messages are lost, validated output produces a higher rate of incoherent fragments, or the repeated-question loop persists or worsens. A green model smoke only establishes that safe speech can be generated; the actual sustained conversation threshold requires live post-release evidence.

## Links

- Isolated chat-format A/B: https://github.com/maaronfanberg-lab/me-/pull/347
- Production adapter: https://github.com/maaronfanberg-lab/me-/pull/348
- Conversation memory retrieval improvement: https://github.com/maaronfanberg-lab/me-/pull/342
- Long-turn copy integrity: https://github.com/maaronfanberg-lab/me-/pull/341

## Result

2026-10-29 shadow canary (research branch only): the native-chat adapter passed 4/4 selected-expression fixture preflights and produced six consecutive accepted model turns in an isolated evolution discussion. This is **not** evidence of sustained natural conversation. Manual inspection found a reply to Mara's unspecified request that explored the phrase "what I want" instead of asking what was needed, a hypothetical eight-meter worm introduced as if relevant to Owen's unnamed hypothesis, and a later reply that substantially restated Jules's prior ripple-effect claim. An earlier run even accepted an unclosed model quotation; a narrow quotation-integrity retry guard was added and re-tested. The adapter smoke now explicitly uses the production `ROOM_CHAT_SPEECH_MODE=1` quality boundary, correcting an earlier shadow-versus-production mismatch. Full qualitative evidence: `docs/research/room-chat-speech-integrity-20261029.json`.

Production remains unchanged. PR #348 stays draft pending a stronger multi-topic natural-dialogue trial, independent integrity checks, and a live post-deployment review of at least 30 consecutive autonomous turns. The separate architecture workflow still fails the viewer-history semantic-archive assertion; it is not being represented as green.
