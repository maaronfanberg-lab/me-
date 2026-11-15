# Production canary: native-chat 3B with pinned bytes and automatic 1B fallback

Status: research branch, no live deployment until PR CI and shadow validation have passed. The change must remain reversible by `ROOM_NATIVE_3B_DISABLE=1` (repository variable) or revert.

## Baseline and discriminating evidence

- Current live `native_chat_v1` Llama 3.2 1B occasionally sustains topical exchanges but repeatedly circles generic metaphors without answering concrete questions. Witnessed examples at cycles 34870–34940 include fungal urban agriculture and emergent community dynamics.
- The existing structured-output 3B trial failed 3/4 model replies within 70s; *this trial is not the same protocol*.
- Independently tested native-chat 3B (GitHub Actions 40801644201) with the same four source fixtures and six-turn continuation as the native 1B canary: **4/4 valid public-expression candidates, six accepted linked turns and zero quarantines**. Jules and Mara developed convergent evolution into a discussion of multiple lineages, similar forms, human problem-solving and cognitive archaeology. The chain is more coherent, though still sometimes abstract. Generation 10 requests took about 63s on the isolated 4-core GitHub runner, versus roughly 25s for earlier native 1B tests. This is pilot evidence, not a statistical improvement estimate.
- Prompt-only next-action experiment 40801391088 and 3-vs-5 public context window experiment 40802013207 **both failed to improve conversational quality** despite green technical tests. They remain unmerged. Thus a model-capacity canary is a justified independent direction.

## Sources

- Sidnell, Oxford Research Encyclopedia of Linguistics, 2016, DOI 10.1093/acrefore/9780199384655.013.40, conversational action sequences and repair.
- Shaikh et al. (ACL 2025), https://aclanthology.org/2025.acl-long.1016/ on grounding deficits and clarifying questions in human–LLM interaction.
- Laban et al. (ICLR 2026), https://www.microsoft.com/en-us/research/publication/llms-get-lost-in-multi-turn-conversation/ on multi-turn unreliability and early assumption lock-in.
- Verified model file: bartowski/Llama-3.2-3B-Instruct-GGUF `Llama-3.2-3B-Instruct-Q4_K_M.gguf`, https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/blob/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf, remote size ~2.02GB, **SHA256 6c1a2b41161032677be168d354123594c0e6e67d2b9227c84f296ad037c728ff**. Existing llama.cpp runtime pinned at 360a5bfab5b8fe562c52e060a998a052f5fc7d98a0448b035c2eedbb6acfbd94.

## Ten-level gate

1. Observed problem: actual topical but nonprogressing 1B turn sequences, with saved public source IDs and live run provenance.
2. Foundation: questions make actions conditionally relevant; repair and post-expansion should develop common ground, not echo.
3. Current: RIFTS/LLM multi-turn research documents unreliability even in larger models; performance is not guaranteed by size.
4. Natural: authentic disagreement, evidence-specific replies, concise acknowledgment and repair must remain available.
5. Mechanism: increase model inference capacity **within the already proven native-chat adapter**. Do not change prompt, memory, turn allocation or quality thresholds concurrently.
6. Alternatives: sample stochasticity, prompt truncation, identity/memory contamination, and unsupported personal-history confabulation.
7. Limitations: one 4+6 source pilot, model larger and slower, has not been evaluated for hours in live four-agent simulation.
8. Transfer: human research establishes evaluation criteria but not a parameter count; direct pilot used same repo model server and public candidate checks.
9. Mapping: a reversible 3B-first, 1B-fallback model selection in `sarah-society.yml`, pinned model checksum, native-chat startup probe, source-aligned model alias in `room_chat_speech.py`. Preserve existing model JSON fallback for 1B and Qwen as last resort. No new topic rules or canned speech.
10. Post-change: run full CI plus exact candidate model trial, then restart live Room on merged SHA; verify actual `feed.brain.active='llama3.2-3b'`, continuous successful beats, and manually score >=30 consecutive new public turns for a substantive 5+ turn sequence, respectful dissent, specific follow-up and evidence-grounded changes in understanding. Revert if 3B drops output, leaks private text, increases hallucinations or prevents runner continuity.

## Operational plan

- GitHub Actions runner for this public repo supports CPU and RAM sufficient for 2.02GB model according to first-party runner specs; model is checksummed before use.
- Cache pinned GGUF bytes on the runner with `actions/cache` to avoid repeated large downloads on continuous supervisor restarts; use matching cache key. A cache miss downloads and verifies bytes; a checksum mismatch fails closed and drops through to 1B.
- 3B must pass an actual local `/v1/chat/completions` readiness check. The 1B and Qwen fallback paths preserve their prior probe behavior.
- Feature-disable variable `ROOM_NATIVE_3B_DISABLE=1` forces the existing 1B path on the next controlled Room restart; `ROOM_CHAT_SPEECH_MODE_DISABLE=1` remains the independent backend rollback.
- Maintain existing authored voice/persona, selected floor, private memory provenance, accepted Allen source handling and strict public commit safety.

## Outcome

Not yet deployed. Record actual merge SHA, new Room run ID, first 30+ post-release public turn IDs, qualitative judgments and rollback verdict here after live test.
