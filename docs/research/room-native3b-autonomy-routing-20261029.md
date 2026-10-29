# Root-cause correction: native 3B must use the single-pass 12-node cognition route

**Status:** isolated targeted live reliability repair; no changes to character personality, speaker turns, memory, prompts or publication rules.

## Reproduced live failure and corrected diagnosis

- PR #351 introduced checksum-verified native Llama3.2 3B with 1B fallback. Room worker GitHub Actions run **40802946116** accepted startup and logged `ROOM_BRAIN_ACTIVE=llama3.2-3b` at **2026-10-29T01:52:58.568Z**. Thus the model downloaded and passed its readiness check promptly, approximately 40 seconds after worker startup.
- Despite healthy startup, public feed remained at cycle **34976**, last published by 1B runner 40800529089 at 01:51:39Z. The 3B run eventually failed at **02:02:32Z** with four consecutive internal beat failures.
- Completed GitHub job logs show repeated `Comprehension fail-soft ... TimeoutError`, then `private model request failed for thought: TimeoutError` in `scripts/room_engine_v5_legacy.py:_private_run`, twice per attempted beat. A temporary selected-floor recovery failed because the old fallback also requested structured thought. These are real stack traces, not inferred from a slow download.
- **Confirmed source cause:** the modern native engine only installed `_llama_model_run` into `_legacy._core.model_run` and `_legacy._private_model.run` when `ROOM_BRAIN_ACTIVE == 'llama3.2-1b'`. For `llama3.2-3b` it silently retained the legacy multi-inference code path, which invoked structured comprehension/thought requests even though the native Room was designed to do cognition internally during its single expression request.
- **Fix:** bind both recognized verified Llama3.2 model labels (`llama3.2-1b`, `llama3.2-3b`) to the same existing native single-pass route, and leave Qwen's legacy fallback unchanged. No new model prompt, speaker quota, vocabulary ban, or chat reply synthesis.

## Research / ten-level gate

1. Observe: direct completed GitHub Actions log, exact exceptions, source file/function, pre/post startup times and unchanged public feed.
2. Foundation: correctness of dynamic dispatch and prevention of extraneous inference in distributed event systems; single-pass internal thought is already the repository's design.
3. Current technical evidence: direct production-class native 3B shadow run **40801644201** generated 4/4 valid responses and 6/6 continued turns when calling the native chat adapter directly; prior structured-output 3B failure underscored that the old JSON-schema cognitive model isn't compatible with 3B on this hardware.
4. Natural behavior: uninterrupted turn-taking requires a responsive publication loop; no conversational topic rule can repair blocked speech generation.
5. Mechanism: recognize the verified model family at import-time so only the single expression node makes network requests while the 12-node state topology remains intact.
6. Competing explanations disproven: the 2GB download did not cause the 10-minute outage; server started quickly, but a wrong model-routing label sent expensive legacy structured requests. The prewarm-only hypothesis is documented as not causally supported for this outage.
7. Limitations: addressing wrong routing does not guarantee semantic quality, memory grounding, successful final candidate preflight or sustained natural conversation; 3B may still be too slow for workload throughput.
8. Context transfer: this fix restores already validated Room architecture rather than transferring human lab dialogue models.
9. Implementation: one model family guard in `scripts/room_engine_v5.py`; isolated interpreter processes test native 1B and 3B monkeypatching plus no HTTP calls for `comprehension` or `thought`, and ensure Qwen remains on its existing fallback; protect all publication controls.
10. Validation: CI all relevant tests, restart merged Room on new commit, verify `feed.brain.active=llama3.2-3b`, 5 successful new beat cycles with no thought/comprehension network timeout, then inspect at least 30 successive public turns for a concrete five-turn action sequence. Roll back with `ROOM_NATIVE_3B_DISABLE=1` plus controlled restart or revert if incompatible.

## Truthful rollout record

Before fix: run 40802946116 failed; 3B model correctly started but legacy thought/comprehension calls timed out, so **zero public 3B turns** were published. This is not a conversation-quality result, only a verified routing failure.

After fix: not yet evaluated. Do not claim natural conversations merely because source, CI or a model alias is present.
