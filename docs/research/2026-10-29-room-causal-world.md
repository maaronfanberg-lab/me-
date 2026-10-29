# Room causal-world interaction trial, October 29, 2026

## 1. Observed problem and baseline
Read the live, published Room feed at cycle 36258 (16:45Z). The recent turns repeat abstract reflections on critique, boundaries, power, social systems, and an extended fungal metaphor, without a shared external event, verifiable action, or meaningful change of mind. Previous finite hidden-world trials were more concrete but expired at cycle 35292. The state reports `conversational_floor_health.active=true`, `diagnostic_only=false`, `speech_backend=native_chat_v1`: the floor can be deployed yet the resulting dialogue still be vacuous.

## 2–4. Theory, current evidence, natural behavior
Sacks, Schegloff & Jefferson (1974), Language 50: locally managed turn-taking is not equivalent to real information exchange. Clark & Wilkes-Gibbs (1986), Cognition 22: grounding is incrementally negotiated, tested and repaired. Brennan & Clark (1996), JEP:LMC 22: partners establish a changing common ground. Zhou et al., EMNLP 2024 (https://aclanthology.org/2024.emnlp-main.1208/): non-omniscient agents can be difficult to coordinate; private clues do not guarantee realistic dialogue. These findings motivate, but cannot prove, a source-linked causal-world test.

## 5. Proposed mechanism
A finite fictional planetarium problem offers Sarah, Mara, Owen, and Jules different private observations. The environment only changes after an explicit, *published*, affirmative first-person physical action. Each change is subsequently shown with the actual source message ID, without fabricated character speech, and survives beyond the most recent three-turn prompt. When the projector has been cleared and restarted, the world acknowledges that consequence so the group can move on. There are no taboo topic lists, mandatory questions or scripted turn allocation.

## 6–8. Alternatives, limitations, context transfer
A concrete scene may improve nominal topic vocabulary without increasing response contingency. A 3B model can still hallucinate inspections, repeat clue text, or remain stuck on the projector. Exact action matching misses many natural-language variants. Human dyad evidence does not establish autonomous four-agent behavior. A finite scene may only temporarily suppress meta-discourse. The test must distinguish a scene-noun novelty effect from actual action→observed result→responsive follow-up.

## 9. Implementation
Branch `room-causal-world-test`. Add `scripts/room_causal_world.py` (bounded 120-cycle replay and private facts), `scripts/test_room_causal_world.py` (no leaks, source IDs, effect order, visitor priority at integration), opt-in augmentation of `scripts/room_chat_speech.py`, and opt-in `ROOM_CAUSAL_WORLD_EXPERIMENT` in the actual Room workflow. Branch-only code does not imply deployed behavior. Current planned pre-state interval: 36320..36439 inclusive; measure actual exposure, not assumed cycle count.

## 10. Precommitted validation
Tests and Room CI must pass first. Compare 100 published baseline turns with 100 actual trial turns; measure concrete observations, four-agent participation, valid public action→consequence→followup sequences, explicit corrections, multi-turn contingent responses, fabricated facts, unanswered questions and reversion to abstract meta-dialogue. At least two consequence→response sequences and a clean transition after resolution are required for a favorable result. CI alone is not quality evidence. Read `room/state.json` and the public `room/feed.json` after merge; do not claim success before inspecting sustained live output. Revert if provenance or visitor priority fails.
