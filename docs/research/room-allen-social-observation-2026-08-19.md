# Allen social observation persistence — corrective research record (2026-08-19)

## Observed problem

Allen is now represented as a legal conversational participant in the Room social boundary, but source tracing shows a second persistence gap: `scripts/room_participant.py` appends Allen turns to `room/conversation.json` and `room/discourse.json` without updating `room/cognitive_state.json`.

The ordinary generated-speaker path goes through `room_engine_v5_core.record()`, which appends each message to every listener's `room_memories`, updates `last_event`, and calls `observe_message()` so relationship exposure/direct-familiarity state changes. Allen's injector bypasses that function because Allen is intentionally not an autonomous cognitive entity. As written, Allen can therefore appear in the transcript while the four minds' Allen relationship counters remain at their neutral migration defaults.

## Corrected live evidence

After the social-participant repair and restart, the live Room persisted Allen in the topic participant list and created an Allen relationship record for Sarah, Mara, Owen, and Jules. A live probe also found 42 retained Allen turns, including the most recent question `What kind of information would you all like to know?`. The injector source nevertheless contains no call to `observe_message()` and no write to `room/cognitive_state.json`.

This means participant identity is now representable, but participant interaction history is not yet learned through the same social observation mechanism used for generated speakers.

## Research basis

This is an implementation-persistence correction under the same behavioral evidence already documented in `room-allen-response-relevance-2026-08-19.md` and `room-allen-social-boundary-2026-08-19.md`: conversational participation and partner-specific common ground require more than text exposure. No new behavioral claim is introduced here.

## Competing explanations and limits

- The transcript itself is not missing Allen; 42 retained turns are present. The failure is specifically that the injector does not persist those turns into listener social memory/relationship state.
- Allen must remain an ordinary participant, not a fifth autonomous generator. The repair must not create an Allen cognitive entity, profile, node assignment, or generation loop.
- Historical backfill must be idempotent. Replaying retained Allen messages more than once would inflate familiarity counters.
- Directness should continue to use the existing social classifier: an explicitly named target is direct, and a reply linked to a previous participant can be inferred from discourse ancestry where already supported.
- Backfill should preserve message chronology and must not replace the current Room event with an older historical Allen event.

## 10-level gate

1. **Observed problem — PASS.** Source and live state identify a transcript/social-memory split.
2. **Foundational evidence — PASS.** Prior participant-specific grounding evidence applies.
3. **Current evidence — PASS.** Current injector and generated-speaker record paths differ exactly at social observation persistence.
4. **Natural-behavior evidence — PASS WITH LIMITATION.** Interaction history should update familiarity; no forced replies are added.
5. **Mechanism evidence — PASS.** Reuse the existing `observe_message()` relationship mechanism rather than inventing a separate Allen-specific social model.
6. **Competing explanations — PASS.** Transcript delivery and participant representation are independently confirmed; persistence remains the missing layer.
7. **Replication/correction/limitations — PASS.** A new simulator reproduces the missing update on the frozen pre-fix code.
8. **Context transfer — PASS WITH LIMITATION.** Allen remains a non-generating participant; only listener observation is generalized.
9. **Implementation mapping — PASS.** The injector idempotently observes retained/new Allen turns and persists the resulting four listener minds.
10. **Post-change validation — PASS PRE-MERGE.** Exact red→green simulator pair plus the existing response and engine tests are recorded below; live persistence remains the final post-merge check.

## Pre-change failing invariant

Given one valid Allen message and a fresh four-mind social state:

1. the message can be appended to conversation/discourse — PASS already;
2. every autonomous entity should record one observed Allen turn — FAIL pre-fix;
3. the explicitly addressed entity should record one direct Allen turn — FAIL pre-fix;
4. repeating the persistence step should be idempotent — absent pre-fix;
5. Allen must not become an autonomous entity — remained true.

## Implementation mapping

- Add an idempotent participant-observation helper in `room_participant.py`.
- Track processed Allen message IDs in cognitive state so retained-history backfill runs once per message.
- For each unseen Allen message, append an ordinary observed-memory record for Sarah, Mara, Owen, and Jules and call the existing `observe_message()` social classifier.
- Derive the original message cycle from its beat ID when possible so historical direct-turn recency is not rewritten as the current cycle.
- Persist `room/cognitive_state.json` whenever unseen Allen history was observed, even if the pending queue is empty.
- Keep Allen out of generator iteration, entity profiles, node ownership, and self-history.

## Simulator-first validation

### Red baseline

A test-only branch froze the pre-fix injector and added only the observation simulator to the existing architecture smoke. Pull request 68 / workflow run `32316291483` failed exactly at the intended boundary:

`AssertionError: participant observation helper exists: None`

Before that failure, the existing engine self-test and Allen response-participant simulator both passed, isolating the missing layer to participant social-observation persistence rather than generation or response recognition.

### Green candidate

Pull request 67 / workflow run `32316227149` passed the combined architecture smoke after the injector patch. The run executed:

- Python compile checks for the engine, social module, private model, participant injector, and observation simulator;
- `room_engine_v5.py selftest`;
- `room_allen_response_sim.py`;
- `room_allen_observation_sim.py`.

All completed successfully. The observation simulator verifies one unseen Allen turn increments all four listeners' observed-turn counters, increments direct-turn state only for the explicitly addressed listener, stores Allen as an observed room memory, records the processed message ID, is idempotent on replay, and does not create an Allen autonomous entity.
