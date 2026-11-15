# Concordia-inspired persistent Room environment referee (2026-11-08)

## 1. Observed problem and baseline

On 2026-11-08, room/state.json reported cycle 57323 and an active native-chat selected floor. The last 16 published room/feed.json utterances repeatedly expanded a speculative "labyrinth", "observer", "narratives", and "feedback-loop" discussion. None contained a source-verifiable physical action or environmental consequence. This is the observed symptom, not proof that the speaker selector or model weights are the sole cause. Existing hidden-world and causal-world experiments are explicitly time-bounded and had expired long before this observation.

Research question: Will a durable environment, changed by the characters' own published actions, provide causal observations that lead to concrete responsive dialogue without forcing topics or speakers?

## 2–4. Foundational, current, and human-behavior evidence

- Concordia, Vezhnevets et al. (2023), https://arxiv.org/abs/2312.03664. Its game-master role separates actors' voluntary actions from independently adjudicated observations.
- Vezhnevets et al., *Multi-Actor Generative Artificial Intelligence as a Game Engine* (2025), https://arxiv.org/abs/2507.08892. Entity-component architecture, non-player environment mechanics, and the distinction between simulationist and dramatist simulation.
- Park et al. (UIST 2023), https://doi.org/10.1145/3586183.3606763. Memory, reflection, and planning jointly mattered for the authors' simulated-agent behavior; the finding is not a guarantee for this Room.
- Sacks, Schegloff and Jefferson (1974) on locally managed turns; Clark and Wilkes-Gibbs (1986) on collaboratively grounded reference. A sequence of words alone does not establish that the shared situation actually changed.

The supplied concordia-main.zip was inspected as the primary code reference. Specifically, concordia/environment/engine.py defines distinct make_observation, next_acting, and resolve roles; the README states that the GM evaluates proposed actions in a common physical, social, or digital environment. Its repository uses Apache-2.0. **This patch adopts the design, not copied implementation or a new heavyweight runtime dependency.**

## 5. Mechanism

A deterministic, bounded-size *World Referee* independently stores ordinary fictional shared-room object state. Only a **public, source-identified, affirmative first-person action** by Sarah, Mara, Owen, or Jules changes an object. A plan, conditional statement, quoted hypothetical, visitor message, or invented character line cannot mutate the state. An action that fails a physical precondition gets a grounded failure observation; a successful action gets a consequence. Causal processes after an action, such as kettle cooling, use the persistent cycle clock. No random scene injection, novelty scoring, enforced participation, or synthetic spoken turns.

Each Room beat reads the committed world snapshot when enabled. At commit time, the public conversation is reconciled exactly once into a saved room/concordia-world.json. The next actor gets a separate *environment observation*, with source provenance when recent, rather than an invented transcript. The public feed exposes the world as its own field. Existing identity, conversation safety, and visitor precedence remain authoritative.

## 6–8. Competing explanations, replication concerns, and context transfer

- The current local 3B model may still favor verbal abstractions or invent outcomes. Repeating the same object actions may create a *new* type of feedback loop.
- Restrictive natural-language action recognition may miss legitimate actions; expansive recognition would increase false physical consequences. This implementation deliberately errs on the side of missing actions.
- The finite list of affordances is a **starting test scaffold**, not a claim to reproduce open-ended life, material culture, emotions, social obligations, private agendas, or a full Concordia simulation.
- Experiments involving human pairs or 25 simulated agents do not directly transfer to four long-lived 1B/3B-model characters with an external participant.
- Persisting a fictional setting can be misleading if interpreted as historical events before activation. This module starts from explicit fictional initial conditions and does not backfill old conversation as though it occurred in the new setting.
- If public beat provenance is missing, duplicated, stale, or corrupted, the referee raises/fails closed rather than manufacturing progress.

## 9. Implementation and exact change boundary

- scripts/room_concordia_world.py: conservative action recognition, deterministic world resolution, monotonically persisted source-verified state, separate environmental notice, and same-turn invented-outcome detector.
- scripts/build_room_feed.py: call referee after a successful beat's committed room/live.json, publish optional concordia_world field.
- scripts/room_chat_speech.py: add environmental notice only if enabled and no immediately preceding real Allen turn; reject model-authored outcomes that the referee has not adjudicated.
- .github/workflows/sarah-society.yml: repository variable ROOM_CONCORDIA_WORLD_ENABLE defaults OFF. Do not auto-activate or merge without evaluating CI and a bounded canary plan.
- .github/workflows/room-conversation-floor-test.yml and scripts/test_room_concordia_world.py: CI for absent/duplicated public evidence, visitor isolation, fake actions, physical constraints, persistence, time advancement, restart/idempotence, and default-off behavior.

No dependency on gdm-concordia is added to the fragile live runner; importing the 45 MB user archive into every Room beat would not itself fix grounding, and could make liveness worse.

## 10. Validation contract and post-change status

Local offline module tests: **9 passed** before creating this PR. This establishes narrow software properties, not changed dialogue. Review the GitHub CI result before merging; expand tests for prompt-path and publication integration.

A controlled activation should compare at least 100 published turns before and after switching on the referee. Log and inspect (a) number of distinct witnessed actions; (b) valid public action -> world outcome -> subsequent actor response sequences; (c) actual partner-specific answers and repairs; (d) repetition and abstract-topic drift; (e) simulated state consistency across runner restarts; (f) user/Allen turn precedence; and (g) acceptance and runner liveness. A favorable signal requires at least two complete causal sequences involving at least two different characters, no fabricated or misattributed outcomes, and non-degraded visitor handling. Zero naturally chosen actions means the mechanism has not been exercised and **is not** a successful result.

**Current status:** code staged for review; live behavioral improvement has **not** been demonstrated. Retain the off-by-default flag until a measured canary can answer the research question.
