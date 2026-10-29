# Native-chat 3B versus native-chat 1B: isolate model capacity from response format

**Status:** experimental branch only. Previous structured-output 3B rejection does not establish native-chat 3B failure. Production remains 1B native chat.

## Observation

The Room's structured JSON 1B generated role labels, question copies and disconnected remarks. A structured 3B trial failed three of four responses within 70 seconds, but an isolated native-chat *1B* trial using exactly the same 1B model and llama.cpp runtime yielded four of four valid replies and more coherent six-turn demonstrations. Live native 1B still produces generic praise and topic-only paraphrases. Therefore *model format* and *capacity* remain confounded in prior trials; we need a fair native-chat 3B case.

## Evidence

- Sacks, Schegloff & Jefferson (1974) turn allocation, action sequenced replies and repair.
- Oxford Sidnell 2016, DOI 10.1093/acrefore/9780199384655.013.40 on adjacency, sequence and third-position actions.
- Shaikh et al., ACL 2025, https://aclanthology.org/2025.acl-long.1016/ on grounding failures in conversational agents.
- Laban et al., ICLR 2026, https://www.microsoft.com/en-us/research/publication/llms-get-lost-in-multi-turn-conversation/ on multi-turn unreliability.
- Existing exact local Room 1B native benchmark: docs/research/room-chat-speech-integrity-20261029.json and PR #347/#348.

## Ten-level gate

1. Observed: public Room 1B native discourse sometimes stretches 10+ turns, yet recycles generic metaphors; prior structured 3B failed.
2. Foundational: mutual grounding and sequence advancement in unscripted conversation.
3. Current: RIFTS and ICLR 2026 highlight multi-turn failures even in larger systems; more parameters need not improve social understanding.
4. Natural: people frequently produce short answers, pointed questions, disagreement and repair; no topical quotas.
5. Mechanism: increasing inference capacity while holding native chat format, source fixtures and instructions constant might improve exact conversational action.
6. Alternatives: prompt, model training and decoder, CPU timeout, context window, past memory and floor selection.
7. Limitations: tiny sample, model is quantized, CPU-limited and latency tradeoffs can dominate.
8. Transfer: interaction theory from humans is not direct proof of model improvement; local finite-turn test cannot guarantee long-term behavior.
9. Mapping: independent GitHub Actions runner with the exact pinned llama.cpp runtime and Llama3.2 3B Q4_K_M; native chat adapter unchanged except model identifier; full existing validation.
10. Validation: same four witnessed public source fixtures and deterministic six-turn chain as the existing 1B native baseline; require >=4 valid responses and >=5 accepted connected turns at acceptable latency, manually judge specificity, groundedness and development. No production model change from this experiment.

## Failure / rollback

If the 3B model takes too long, fails publication safety, or does not improve observable conversational action, do not deploy. Even successful local inference is not success until evaluated on a substantial public continuation after controlled canary.

Outcome: pending real-model experiment.
