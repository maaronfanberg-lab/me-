# Room: source-bound response opportunities without mandatory speech

Date: 2026-11-15. **Experiment only**, draft PR #415. Production Concordia
scheduler, live public state, inference runtime, and publication path untouched.

## Observed problem (gate 1)
At public cycle 67,894, none of the most recent 160 Room turns contained
a question mark; 114 contained an intention phrase; the deterministic audit
found 17 turns naming another participant. Name mention is NOT proof of a
directed conversational exchange. Current public data has no validated
`reply_to` provenance and cannot establish whether a response was actually
heard. This makes simple speech-frequency, name-mention, or Jaccard scores
inadequate for testing social reciprocity.

## Foundational, current and natural evidence (gates 2–4)
- Clark & Wilkes-Gibbs (1986), *Cognition*, DOI
  10.1016/0010-0277(86)90010-7: referring and grounding require
  collaborative contributions, not just repeat references.
- Brennan & Clark (1996), *JEP: Learning, Memory, and Cognition*, DOI
  10.1037/0278-7393.22.6.1482: partner-specific conceptual pacts emerge
  from interactive history; a shared word is not itself proof of mutual
  understanding.
- Stivers, *Sequence Organization*, in the *Handbook of Conversation
  Analysis* (2013): actions occur in structured sequences; a question makes
  some future response relevant but does not guarantee it.
- Park et al. (2023), *Generative Agents*, DOI
  10.1145/3586183.3606763: source-bound episodic memory is an ingredient
  for planning and situated behavior, not a substitute for independent
  decisions or grounded world consequences.
- Zhou et al. (2024), *SOTOPIA*, ICLR: interaction must be tested across
  diverse goals and circumstances; fluent speech alone is insufficient.
- *Validation is the central challenge for generative social simulation*
  (2025), DOI 10.1007/s10462-025-11412-6: limited simulated-dialogue
  proxies should not be read as proof of human realism.

## Mechanism (gate 5) and competing explanations (gate 6)
Build a pure `joint_context` function using only each person's
`witnessed_history`. Surface explicit addressed messages (structured
`to` field or clear opening vocative), public Allen messages, and their
source IDs. A later `reply_to` link can retire a bid only if it occurs
later and the original speaker could witness the reply.

This models *opportunities* for continuing a joint project without forcing
speech, a question quota, identical emotional responses or a scripted
friendship. An unrelated mention of "Sarah's notebook" does not become a
request for Sarah's response. Every character may still work, initiate,
observe, disagree or be quiet.

An explicit source link indicates a claimed conversational relation, not
demonstrated comprehension, acceptance, truth, or emotional closeness.
Some direct addresses are conveyed through intonation, position, gestures
and indirect speech acts; a conservative text-only extractor will miss them.
Public Allen inputs addressed to the room are available, not compulsory
orders to reply.

## Replication, boundary and transfer (gates 7–8)
The cited work includes dyads and controlled dialogue contexts, whereas
this simulation includes four autonomous characters, Allen, long-running
state, and a constrained local model. Real-human findings justify the
*conceptual decomposition*, not any fixed threshold or numerical model of
friendship. Avoid claiming human performance based on these tests.

Test both public/private data and duplicate event IDs; ensure an
inaccessible event cannot donate metadata to an accessible collision.
Do not infer that private reply journals resolved an external question.
No transcripts or private prompt material are logged in these tests.

## Implementation mapping and validation (gates 9–10)
Only add `scripts/room_social_joint_context.py` and
`scripts/test_room_social_joint_context.py` in an isolated draft branch.
Wire their tests into the PR-only workflow. Explicit scenarios: clear
vocative, non-addressing mention, structured addressee, public Allen
input, private witness restriction, linked public reply, private
undelivered reply, reference to a future event, duplicate hidden
event ID, and bounded/empty inputs.

Acceptance: all regression cases pass. This would establish structural
source isolation, NOT that the system has become a working social engine.
Next, connect this context to a shadow agent policy with distinct personal
projects and an independently chosen free-form utterance or action; validate
against comparable live snapshots. Do not publish or migrate until a
longitudinal pilot shows causal action follow-through and preserved history.

**Production post-change outcome:** not applicable; no production change.
**Sandbox test result:** CI run 43722561139 at 2026-11-15 14:07 UTC passed all 21 tests (8 witnessed-memory, 5 trace-audit, 8 joint-context). This verifies source and boundary fixtures, not conversational performance. The pilot has not yet produced an independently generated matched 160-turn trace or exercised an alternative LLM scheduler.
