# Room: repeated intended work as an independent diagnostic (15 November 2026)

**Status:** non-production trace instrument on draft social-architecture PR #415.
No scheduler, cognition, speech-generation, publication, or live state modified by this change.

## 1. Observed problem and baseline
At 2026-11-15 13:59:19 UTC, public `room/feed.json` reported cycle
67,894, 160 exposed recent turns. Descriptive counts: 75 contain "decide",
49 "inspect", 41 "notebook", no question marks, and none mention Allen.
The previously green trace audit reported **0 same-speaker near-duplicates**,
despite observable repeated intentions around examining notebooks, writing
at the board, and finding connections. This is not a contradiction: the audit
used a high lexical Jaccard threshold and was not designed to recognize
paraphrased repetition of an intended verb/object.

**Question:** Can we detect repeated *intentions to use the same affordance*
without confusing an intended action with a completed world event, treating
legitimate revisiting as a behavioral error, or adding more speech bans?

## 2–4. Foundations, current evidence, natural interaction
- Park et al. (UIST 2023), https://doi.org/10.1145/3586183.3606763:
  memory, reflection, planning and environmental interaction are distinct
  mechanisms. Repeated intent is not equivalent to verified outcome.
- Clark & Wilkes-Gibbs (Cognition 1986),
  https://doi.org/10.1016/0010-0277(86)90010-7:
  conversational success depends on joint grounding and iterative repair,
  not merely changing lexical surface form.
- Stivers (2013), "Sequence Organization", *Handbook of Conversation
  Analysis*: responsive moves must be evaluated in sequence.
- Schmidt et al. (2025), *Dynamics of topic exploration in conversation*,
  https://escholarship.org/uc/item/15d3808f:
  real conversational partners revisit and progressively explore related
  topics. Topic recurrence **alone** cannot imply defective interaction.
- *Validation is the central challenge for generative social simulation*
  (2025), https://doi.org/10.1007/s10462-025-11412-6:
  internal metrics are insufficient without external/trajectory validation.

## 5. Proposed mechanism and mapping
The Room's existing `room_life.AFFORDANCES` defines valid task verbs and
objects. A separate *read-only audit* extracts high-confidence verb/object
pairs from intention-containing utterances. It reports a later occurrence
of the same (speaker, verb, object) within 80 transcript turns.

New output fields: `distinct_intended_work_signatures`,
`repeated_intended_work_turns_within_80`, and redacted index-only
`repeated_intended_work_examples`. These do **not** change speech or
execution. No work is marked completed without `room_life` receipts.

## 6–8. Competing explanations, limitations, transfer
- A person may intentionally inspect a notebook twice, or persist in a
  challenging task. Thus this is a **candidate loop detector**, not a
  penalty, score of humanity, or automatic reason to reject dialogue.
- A character may name an object as a topic rather than a target. The
  extractor is an imperfect lexical proxy and can miss implied tasks.
- The 80-turn window is an audit convenience, not a researched human
  threshold. Compare 20/40/80-turn sensitivity before treating rates
  as informative.
- This simulation's four long-lived fictional people are not equivalent
  to human dyads in laboratory studies. Transfer is provisional.
- A transcript alone cannot determine whether goals made progress.
  Verified event IDs and causal joins must be added to assess follow-through.

## 9–10. Validation and post-change plan
Tests must verify (a) paraphrased repeated intents are counted even when
Jaccard echoes are zero, (b) unexpressed or invalid affordance statements
are not counted, (c) one-off work isn't falsely called repeated, and (d)
the module never writes the live repository. Run a fresh 160-turn public
audit in PR-only CI and report both prior and new metrics, with denominator
160. Do not merge merely because these descriptive tests pass.

**Sandbox result:** on PR run 43722166185 (2026-11-15, passing),
13 tests succeeded (8 witnessed-memory + 5 trace-audit).
On the same 160-turn snapshot, the old lexical duplicate metric remained
zero, but the new audit identified **30 repeated intended-work turns**
within the preceding 80 turns and **41 distinct (speaker, verb, object)
signatures**. There were 114 intention-phrase turns and 17 explicit
name-address proxy turns. This is evidence that the earlier metric missed
some recurring *actions*, not a measured improvement in conversation.

**Production outcome:** not yet tested: this is instrumentation only.
Success for a future replacement engine requires matched longitudinal
replays and grounded world-action follow-through, not merely fewer lexical
motifs or more dialogue.
