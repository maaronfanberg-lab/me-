# Read-only source-linked directed-question evidence (2026-10-28)

## Observation
Review of 300 recent public Room turns found 77 turns ending in a question mark. Ten sampled three-turn traces included echoed questions, one-word reactions, direct addressed invitations, and topic drift. A selected example was Jules' public question to Sarah on exercising, while hidden metadata addressed Mara. A different example: Sarah's prefaced question on support was repeated by Jules and Mara.

## Research question
Can a bounded public evidence ledger preserve which spoken question was addressed to which character and which turns followed, without falsely claiming comprehension, consent, or semantic closure?

## Research-gate checklist
1. **Observed symptom**: Directed questions and subsequent turns lose source-linked action continuity across context windows.
2. **Foundational**: Sacks, Schegloff, Jefferson (1974), DOI 10.2307/412243, recipient design and next-turn organization.
3. **Current refinement**: `Language` 2025 reprint and commentary DOI 10.1353/lan.2025.a954231; does not itself validate our implementation.
4. **Natural behavior**: Questions create relevant response positions; spoken turns by the addressee need not actually answer.
5. **Mechanism**: Event-source recorded public question ID, actual audible addressee, and later recipient turn IDs; omit unverified semantic meaning.
6. **Competing hypotheses**: Nonresponsive dialogue also arises from small-model limitations, topic contamination, or malformed expression schemas; ledger alone does not solve them.
7. **Limits**: Text-only vocative regex misses implicit and nonstandard addressing; later recipient turns can be unrelated. The ledger must never call a later turn an answer merely because it follows.
8. **Transfer**: Conversation-analysis evidence does not establish performance in a four-agent, 0.5B to 1B local-model setting.
9. **Implementation**: Read-only pure projection in `scripts/room_action_ledger.py`, bounded 32-turn default, stable public source IDs, ambiguous recipient exclusion, no private-memory state mutation.
10. **Validation**: Unit tests for 100 conflicting targets, Allen, ambiguous names, bystander replies, deduplication, window bounds, and privacy; GitHub CI runs them. A later integration would need independent human-rated behavior improvements.

## Explicit stop condition
Do not promote the prototype into speaker-selection or generation until we show it improves real action sequence completion and does not create stale response obligations. Its output has `semantic_resolution=not_assessed` for every record.

## Status
Pure prototype only. No live generation or memory paths call it. Not deployed behavior.
