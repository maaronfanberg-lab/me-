# Room implementation log: executable offline foundation
**Date:** 2026-10-24. **Branch:** engineering/room-dialogue-foundations-20261024. **Draft PR:** #314, targeting the reviewed research branch, not production main.

## Intent and boundaries
The implementation is a foundation for human-like conversational interaction in the Room. No lexical anti-repetition rule, topic reset, fixed speaker quota or canned "sound more human" phrase was added. Genuine short replies, clarification echoes and purposeful repetition remain allowable. No production observer, model, Git runner, Claude token, Cloudflare Worker or Allen queue was changed. The new modules are not imported by the live Room pipeline.

This implementation sits under the research-first ten-level gate documented in the companion files:
- room-human-conversation-implementation-plan-20261024.md
- room-implementation-precedents-20261024.md
- room-interactional-sequence-evidence-20261024.md

## Executable components
- scripts/room_beat_protocol.py: an explicit positive distinction between a successful floor decision to remain silent and an unhealthy missing/invalid model stage. Per-beat typed result; tentative health state separated from confirmed durable health; sliding failure ratio and bounded diagnostic heartbeat.
- scripts/room_delivery_protocol.py: canonical decision IDs independent of repeated words; published event ID/source ID checks; independent membership requirement for authoritative Git commits; prevention of forked generations, duplicate inbound ID mappings and same-ID changed bytes; mirror deliverability requires matching event hashes; pending user input ACK strictly derived from Git-published **inbound** events, never from an autonomous reply referencing a message.
- scripts/room_experiment_guard.py: disallow production-capable tokens/relay variables and refuse same-tree live workspace for future sandbox execution. This guard must still be wired to every eventual model/transport adapter entry point.
- scripts/room_offline_replay.py: read-only, privacy-minimal public event sampler with source IDs and reserved negative-control utterances. Observation/witnessed history must be supplied explicitly, never inferred retroactively from published speech.
- scripts/room_offline_transport.py: zero-network fake Git/Worker and precise artificial crash and race seams. Models current Worker first-20 of MAX_QUEUE 50; separately models PROPOSED mirror journal/history/resync behavior that **does not yet exist** on the real Worker.
- scripts/test_room_*.py: deterministic unit tests, real-public-feed read-only regression and simulated fault matrix.
- .github/workflows/room-offline-protocol-test.yml: independent timeout-bounded CI without production write permissions, in addition to the existing Room presence/group tests.

## What went wrong and how it was corrected
1. **Corpus sampling bias:** first implementation selected only question-shaped utterances, dropping negative-control statements. An actual CI test failed. Sampler corrected to reserve uncued examples. The revised test passed.
2. **False heartbeat health:** first implementation treated a failure write as a successful healthy heartbeat. Claude reviewed the actual code and identified the error; health tracking now separates tentative state, durable confirmation and last healthy commitment, with explicit failed-model outcomes.
3. **Unbounded repeated-failure writes:** initial health helper requested a Git commit for every invalid generation. The pure reducer now coalesces state writes except transitions/degradation/actual public speech, and the unit tests exercise 1,000 failure beats. This is only a protocol, not yet real Git write integration.
4. **Insufficient publication proof:** first reference mirror code trusted any caller-supplied pushed boolean, could merge generation forks, and checked matching IDs without matching bytes. Now it checks independently supplied Git-main commit evidence, rejects generation and source-ID collisions, and demands independently verified mirror event hashes.
5. **Double-ACK and race hazards:** the first race helper conflated an already published reply with an already consumed input. It now distinguishes upstream decision IDs from inbound source IDs. The FakeGit model now uses compare-and-set on consumed inputs and a separately maintained FakeRemote membership model.
6. **Simulator-specific deficiencies:** Claude's second targeted review identified a queue-ID reuse / changed-bytes deletion hazard, competing publisher races and mirror corruption that were not tested. The simulator now rejects an ID with changed text, keeps a remote ledger separate from locally staged events, and audits mirror bytes plus phantom events before treating delivery as completed. Additional tests exercise these cases.
7. **Stale generation:** FakeWorker resync formerly used max(old_mirror_generation, git_generation), which could strand new legitimate generations. It now resets to the verified generation in the offline model, with a test where the mirror starts far ahead and normal delivery resumes after resync.

## Confirmed tests and limits
GitHub Actions has already shown passing Room-presence and group-dynamics suites and passing early offline protocol suites. Each new test commit re-runs those checks; consult the latest PR checks for the status of the final code revision rather than assuming it passed merely because an older revision did.

**The in-memory tests do not prove:**
- atomic multi-file Git and Cloudflare storage transactions in production;
- actual GitHub Actions restart/rebase semantics or OIDC permission checks;
- real Cloudflare resync/history endpoints (these are still proposals);
- crash recovery of a separate process with no preserved in-memory state;
- what happens to genuinely corrupted, unparsable accepted queue data or prolonged upstream storage exhaustion;
- any improvement in actual natural conversation, human action recognition, grounding, personalities, voluntariness or model competence.

The Worker issues UUID source IDs in real code; fake sequential IDs are used for reproducible tests, and the collision test is deliberately adversarial. The fake's booleans authorizing resync are not security proofs.

## Next gated work, before any actual production integration
1. Define and test a durable, versioned on-disk source-event journal with crash/restart across fresh processes and simulated Git conflicts; handle poison-queue dead lettering without silent deletion. Protect inbound source/byte identity and immutable prior decisions.
2. Reconcile the real Worker API against a minimal separately reviewed implementation of paginated per-ID event history, authenticated generation resync, backpressure, and visible/queued status. Do NOT replace the live Worker wholesale.
3. Collect double-annotated conversational sequences from published Room turns and build an action-conditioned generator capability ablation using a pinned local model. Do not confuse generated speech diversity with human conversational progress.
4. Only after reliability gates, implement action-aware floor selection before expression generation with genuine silence and separate per-character common-ground updates.
5. Conduct matched replay/blinded A/B, security and liveness tests before any default-off canary; keep original personality, relationship memory and Allen messages.

**Gate status:** implementation work started, review-driven fixes under test, production unchanged; no claim of bug-free deployment.
