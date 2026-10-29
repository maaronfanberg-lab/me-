# Room Qwen2.5 1.5B Instruct capacity trial

Status: isolated model test, never publish generated test speech.

## Evidence and hypothesis

The existing production Llama 3.2 1B model often echoes rather than responds. A 3B variant yielded only 1/4 valid responses within 70 seconds, and a leaner 1B prompt improved one ecological case but still created repetition and unrelated hostility. The Hugging Face model repository `bartowski/Qwen2.5-1.5B-Instruct-GGUF` provides a Q4_K_M GGUF of approximately 986 MB, close to existing 1B model resource scale. Hypothesis: a distinct instruction-tuned small-model family may follow Room's structured speech/repair directives better without unacceptable CPU latency. No comparative conclusion before test.

## 10-level research gate

1. Observed failure: grounded public repeated question and saved actual model A/B cases.
2. Foundation: conversational sequence organization, grounding, and third-position response.
3. Contemporary evidence: first-party Hugging Face model cards and exact local runtime compatibility; model availability does not imply quality.
4. Natural behavior: any accepted speech must be responsive, allow short repair/disagreement, and develop facts across several turns.
5. Mechanism: instruction-following robustness and different training distribution, not brute-force topic rotation.
6. Alternatives: prompt overload, stale memories, confusing intent, invalid JSON-schema behavior, and sampling/latency.
7. Limitations: four public cases and one chain are only a pilot, no formal dialogue benchmark; exact same prompt may favor one family.
8. Context transfer: synthetic four-entity continuous Room in GitHub Actions differs from standard assistant chat.
9. Implementation: isolated Qwen2.5 1.5B Instruct model server, identical current production wrapper, public fixtures and seeds from 1B baseline; no production change.
10. Validation: >=4 valid responses, >=5 generated connected turns, no full-question copies, source-specific semantic quality assessed manually, acceptable latency; if not, no deployment.

## Runtime and rollback

GGUF from public Hugging Face model. Runtime is the pinned Room llama.cpp binary with established checksum. Record model file SHA256, keep secrets out, use no private Allen content. Promotion would require a separate gated PR, live restart and 30+ genuine transcript turns, rollback if coherence or safety fails.

## Evidence URLs

https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF
https://github.com/maaronfanberg-lab/me-/pull/336

Outcome: pending.
