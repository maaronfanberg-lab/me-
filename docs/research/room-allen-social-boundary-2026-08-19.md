# Allen social-participant boundary — corrective research record (2026-08-19)

## Observed problem

Allen can submit turns through the Room interface, but Sarah, Mara, Owen, and Jules behave as though Allen is not a known conversational participant. The earlier response-relevance repair made Allen legal at the engine/model boundary, but live validation did not show Allen becoming part of the Room's persisted social state.

## Corrected live evidence

The previous research note inferred from source shape that Allen turns were entering the active conversation. Live inspection now contradicts that inference:

- the current retained conversation blob contains no `speaker: "allen"` entry;
- the current discourse blob contains no Allen speaker node;
- the current cognitive-state blob contains no Allen relationship entry;
- the active topic state's participant list contains only Sarah, Mara, Owen, and Jules;
- an authenticated live relay probe returned HTTP 200 with `{"messages":[]}` for the pending Allen queue at 2026-08-19T23:26:20Z;
- the Room runner does contain and execute the Allen pending-fetch/inject path before every beat.

The live queue being empty does not by itself prove where a submitted turn was lost, so no queue-loss mechanism is assumed here. It does establish that there was no waiting Allen turn at probe time.

## Mechanism trace

`scripts/room_social_v5.py` uses one hard-coded `ORDER=("sarah","mara","owen","jules")` for two different concepts: autonomous generators and conversational participants. That causes four distinct exclusions:

1. `migrate_minds()` creates relationship records only for speakers in `ORDER`, so no persistent `people["allen"]` relationship is established.
2. `classify_event()` returns `None` when a speaker is not in `ORDER`, so an Allen utterance cannot become an observed/direct social event.
3. `_target()` accepts only targets in `ORDER`, so social direct-addressee resolution cannot represent Allen.
4. `topic_template()` records only `ORDER` as participants, and existing topic state is not normalized to add Allen.

This deeper module is independent of the engine wrapper used by the previous repair, so engine-level membership could pass while social state continued to reject Allen.

## Research question

What is the smallest change that represents Allen as an ordinary conversational participant throughout social-state processing while preserving exactly four autonomous generators and twelve cognitive nodes?

## Evidence basis

This corrective patch relies on the same conversation-mechanism evidence documented in `room-allen-response-relevance-2026-08-19.md`: collaborative grounding, participant-specific common ground, and response relevance require the interlocutor to be representable as a participant rather than merely present as text. The new evidence is implementation-specific and narrows the failing layer; it does not change those behavioral claims.

## Competing explanations and limits

- The empty relay queue could reflect no new pending turn at the exact probe time; it is not evidence that Cloudflare necessarily discarded a turn.
- The injector and private commit stage remain separate possible failure points for a future fresh Allen turn. They should be tested end-to-end after the social boundary is corrected.
- Adding Allen to the participant set must not add Allen to autonomous scheduling, cognitive-node ownership, generation order, or a personality profile.
- Human conversation does not require every Allen turn to receive a reply from every entity. Validation is representability and materially improved direct response, not forced four-way acknowledgement.

## 10-level gate result

1. **Observed problem — PASS.** User observation and persisted live state agree that Allen is not represented socially.
2. **Foundational evidence — PASS.** Prior grounding/sequence research applies to participant representation.
3. **Current evidence — PASS.** Current repository/runtime evidence identifies the concrete exclusion boundary.
4. **Natural-behavior evidence — PASS WITH LIMITATION.** Apply participant/addressee representation only; do not script replies.
5. **Mechanism evidence — PASS.** Separate generator membership from conversational-participant membership.
6. **Competing explanations — PASS.** Queue loss is not assumed; the social exclusion is independently observable in source and persisted state.
7. **Replication/correction/limitations — PASS.** This note explicitly corrects the earlier source-only inference with live evidence.
8. **Context transfer — PASS WITH LIMITATION.** Multi-party Room behavior remains autonomous; only participant representation is generalized.
9. **Implementation mapping — PASS.** Change `room_social_v5.py` participant recognition and migration while keeping `ORDER` four-only.
10. **Post-change validation — PASS IN SIMULATOR; LIVE PERSISTENCE PENDING.** The exact simulator moved from red to green while the existing engine self-test remained green. Persisted live state is checked only after merge/restart.

## Pre-change simulator result

`room/allen-social-sim-diagnostic.json` recorded a failing run at 2026-08-19T23:32:45Z. It passed the four-generator invariants and failed at `social participant set contains Allen`, where the observed participant tuple was empty because `room_social_v5.py` defined no participant set.

## Implementation mapping

Only the social-participant boundary is changed:

- keep `ORDER=(sarah,mara,owen,jules)` as the autonomous generator/listener set;
- define `PARTICIPANTS=ORDER+(allen,)`;
- create and migrate relationships for all conversational participants while still iterating cognitive listeners only over `ORDER`;
- accept participant speakers/targets in event classification and direct-addressee resolution;
- normalize both new and existing topic participant lists to `PARTICIPANTS`;
- keep autonomous partner scheduling over `ORDER` unless an explicit conversational target is already present;
- audit Allen relationship values without creating an Allen cognitive entity.

## Validation criteria

The same `scripts/room_allen_response_sim.py` must pass all of the following after the patch:

1. generator iteration remains exactly Sarah, Mara, Owen, Jules;
2. Allen exists in the social participant set;
3. relationship migration creates Allen for all four autonomous entities;
4. an Allen-to-Sarah direct turn is classified as a direct social event;
5. that event updates Sarah's Allen relationship counters;
6. topic participant state contains Allen;
7. private thought/expression schemas may select Allen;
8. engine sense retains Allen as the active partner.

After merge/restart, persisted cognitive state and topic participant state must contain Allen. A fresh real Allen turn is then required for the final queue → injector → conversation → direct-response test.

## Post-change simulator result

At 2026-08-19T23:46:20Z the isolated fix branch passed the exact Allen social-boundary simulator and the existing engine self-test. The simulator confirmed all eight criteria above, including four-only autonomous generation, Allen relationship migration, direct event classification, topic participation, legal model targeting, and retention of Allen as the active engine partner. The engine self-test independently passed the sequential four-voice architecture invariant.

One intermediate simulator run falsely reported Jules as the active partner because the test monkey-patched the compatibility wrapper while `sense()` remained bound to the preserved core module. The harness was corrected to replace the bindings actually resolved by `sense()`; no production behavior was changed to satisfy that harness error.
