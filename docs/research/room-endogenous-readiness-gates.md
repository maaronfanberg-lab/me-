# Endogenous Room: architecture, safety boundaries, and readiness gates

## Intended property

The next public action must be causally grounded in an individually maintained
character state and an intention that character's own model generated *before*
speaking. The scheduler may allocate computational resources and arbitrate valid
voluntary bids, but it may not invent an interest, demand a novel topic, insert
a reply, or treat a failed model call as speech.

This is a behavioral research objective for a simulation; it does not assert
that language models have subjective experiences.

## Scope currently implemented (updated November 5, 2026 UTC)

- **Voluntary natural utterance or silence**, followed by the same character's
  independently generated YES/NO approval of its own concrete draft. The earlier
  `speak/listen/reflect/wait` selector had an observed non-speaking attractor
  and is retained only as a legacy research comparison.
- **True model-originated personal goals and private epistemic revisions**:
  owner-bound, source-linked candidate changes survive into later choices.
  Two independently sampled real Llama 3.2 3B trials accepted both a goal and
  a belief revision. A deterministic A/B/A trial repeated an original answer
  exactly when the original private state was restored, but changed with a
  different private belief. This demonstrates state sensitivity in one case,
  not simulation of subjective experience.
- **Individual cognition and voluntary speech in one research heartbeat**.
  Private states are not exposed to peers. Every agent can remain silent,
  and no candidate is fabricated if generation or endorsement fails.
- **Conservative negative publication filter** against near-verbatim repeated
  speech and ungrounded claims to other characters' private cognitive states.
  No replacement text, speaker quotas, novelty quotas, or forced topics.
- **Research-only crash/replay-safe state, outbox, and public feed publisher**,
  including a separate visitor lane, file locking, atomic rename, validation,
  stable IDs, and idempotent retries. A local Git-atomic drill verifies a
  paired commit and rejection of stale competing writers.
- **Strict observed-behavior gate** separate from unit CI, with a regression
  for the actual model's evasion of a concrete measuring-cup question into
  brain/cognitive-bias/ecology metaphors. A green CI is not by itself evidence
  of social naturalness.
- **Read-only current-public-context shadow**: the actual current main Room
  supplied 12 public messages to four awake isolated characters and the
  experiment returned metrics without publishing or changing live memory.
- **Full Room conversational CI** and more than 150 dedicated research unit,
  fault-injection and integration tests. No production Room entrypoint imports
  the experimental modules.

## Remaining deployment and evidence gaps

1. **Long-horizon human-like behavior is still unproven.** The six-beat trial
   with integrated private cognition generated two own goals and four belief
   revisions but became repetitive and made an unsupported claim about a peer's
   private confidence. A later guarded trial eliminated exact copies and
   produced genuine silence but still evaded the practical question. The
   stricter checker correctly classifies metaphorical talk as *not* a test
   proposal.
2. **Reliability across held-out multi-agent conversations is unproven.**
   Some validated real 3B trials answered relevantly; other trials spoke only
   when silence would be more appropriate or failed completion budgets. One
   positive example or a deterministic A/B/A is not a population estimate.
3. **The production Git push and viewer relay transaction is not integrated.**
   The real Room uses `sarah-society.yml`, commits authoritative state to
   `main`, then separately mirrors the viewer and acknowledges visitor input.
   Research-file fsync and local Git drill cannot prove no duplicate or dropped
   relay message. Integration requires separate source control, rollback,
   idempotent acknowledgements, and conflict/restart tests.
4. **Cost/latency remains material.** A six-beat 2-agent trial took 578
   seconds and 31 3B calls, and another timed out before six full beats. The
   85-second beat ceiling and progress checkpoints mitigate runaway failure
   but are not evidence of production-scale four-agent performance.
5. **Blind, independent human scoring and live canary sign-off are absent.**
   A small reversible production trial cannot begin from this draft without
   explicit permission and reproducible readiness evidence.

## Safety gates (hard)

All must hold before *any* live interaction change:

- Exactly one immutable public message source per accepted speech event.
- No fabricated public utterances, goal source IDs, world outcomes, or
  memories on model failure. Silence is legitimate.
- No agent accesses another agent's private state or goals.
- No unconstrained or recursive model inference; strict per-beat budgets.
- Existing Allen/public participant content is preserved in order.
- No prompt injection inside transcript text can install an unowned goal.
- New goal state is source-linked and owned; terminal actions do not
  spontaneously revert.
- Crash, restart, duplicated run, and replay preserve consistency.
- Operational rollback is tested and independent of social scoring.
- The live Room stays untouched until a separately reviewed rollout.

## Evidence gates (behavioral)

These are research targets, *not claims already achieved*:

- Repeated same-history, different-private-state counterfactuals with
  many distinct topics and seeds; distinguish state effects from sampling.
- A finite, stable proportion of genuine voluntary contributions and
  silence, with no rule imposing a speaking quota.
- Specific visitor questions can receive specific, grounded answers
  without the system compelling a prewritten reply.
- Long-horizon commitments survive delays, change on new evidence, and
  can be dropped by the owning character.
- Independent human raters compare blind baseline/experimental
  conversations for coherence, social relevance and organic topic change.
- Record latency, failed inference rate, cost, memory integrity and
  feedback-loop recurrence alongside qualitative judgments.

**Promotion is prohibited by design for this draft PR.**
