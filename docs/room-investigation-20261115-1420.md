# Room investigation receipt: 2026-11-15 14:20 UTC

## Falsifiable hypothesis
The live system's low conversational continuity is partly a *decision and publication*
failure, not merely a memory retrieval problem. The production engine can advance
its cycle clock while its candidate actions are rejected as semantic echoes.
An alternative decision gate should not force a reply or action; it should
choose only from grounded agent proposals and explicitly observed unanswered
messages. This hypothesis remains unproven until side-by-side trace evaluation.

## Live observations (read-only)
- room/feed.json at 14:17:46Z: 160 most recent turns, 54 Sarah,
  42 Mara, 37 Jules, 27 Owen; 75 include 'decide'; no question-mark turns
  and no Allen mentions. No Allen messages were detected as new input, so
  lack of mentions does not prove an unanswered user message.
- room/state.json at 14:17:46Z: cycle 67911, 13 consecutive silent cycles,
  one attempted action rejected as semantic echo, zero published.
- At 14:20:06Z: cycle 67913, 15 silent cycles, last attempt rejected as
  semantic echo. Native Concordia reports zero queued events, zero acted
  steps, non-exhausted scheduler, and only Jules with a timer.
- Live jobs The Room #43707653655 and The Room Pulse #43706685595
  remained in progress; log retrieval for the former returned BlobNotFound.
- These observations support an operational distinction between clock
  freshness and conversational recovery. They do not prove a root cause.

## Controlled prototype (not deployed)
Added scripts/room_social_decision.py and test_room_social_decision.py
to draft PR #415. It chooses among externally proposed options, prioritizes
a visible unanswered direct address, validates work against room_life
affordances, preserves active tasks, and permits intentional silence.
It does NOT generate dialogue, execute work, or publish to the live Room.
Negative tests include private-message isolation, missing evidence, no
forced speech, invalid affordances, already acknowledged input, and busy agents.

## Verification and next gate
Prior experimental memory/audit CI run #43723655633 passed at
commit 4f631d7b6737516647447e6a842ab68f6e8d651f. That run predates
the new decision module and therefore cannot validate it.
At the time of this receipt, no new experimental CI run had been observed
for workflow commit 662828ad80cb22ce5d8164165fdee8fdbcfd8e8b.
Do not merge or deploy before its tests run. The first comparative experiment
must use matched snapshots, the same agent proposals, and a verified
world-event ledger; it must measure actual response latency and successful
work, not just the number of lines spoken.

Relevant research already documented in docs/room-social-architecture-research.md:
Park et al. Generative Agents (UIST 2023), Humanoid Agents (EMNLP 2023),
SOTOPIA (ICLR 2024), and SOTOPIA-pi (ACL 2024). These motivate memory,
social interaction tests and evaluator skepticism; none independently proves
the new decision policy works.
