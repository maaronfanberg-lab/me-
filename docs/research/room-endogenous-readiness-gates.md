# Endogenous Room: architecture, safety boundaries, and readiness gates

## Intended property

The next public action must be causally grounded in an individually maintained
character state and an intention that character's own model generated *before*
speaking. The scheduler may allocate computational resources and arbitrate valid
voluntary bids, but it may not invent an interest, demand a novel topic, insert
a reply, or treat a failed model call as speech.

This is a behavioral research objective for a simulation; it does not assert
that language models have subjective experiences.

## Scope currently implemented

- A provenance-bound, fail-closed private-bid schema and bounded voluntary
  arbitration (`room_endogenous_preflight.py`).
- Owner-isolated request construction, model-authored choices among
  `speak/listen/reflect/wait`, and optional loopback-only local transport
  (`room_endogenous_shadow.py`).
- A pure, owner-bound, versioned private-goal journal with witnessed/owned
  provenance and pause/resume/resolve/abandon operations
  (`room_endogenous_goal_journal.py`).
- A source-pinned observational baseline and synthetic regression tests.
- A real 3B isolated canary using synthetic history and counterfactual private
  states (`room_endogenous_3b_canary.py`).
- No production Room entrypoint imports the experimental modules.

## Known experimental gaps

1. The research canary still uses externally prepared *initial* individual
   goals, even though its speech intentions are model authored. Full
   endogenous goal genesis remains unproven.
2. A private goal journal can validate a model-authored proposal, but it
   cannot authenticate *authorship* by itself. A trusted model wrapper needs
   to bind every proposal to the requesting agent before journal commit.
3. The 3B model's decisions may be weakly sensitive to private beliefs, or
   biased toward silence; counterfactuals must establish this empirically.
4. Failing closed is not the same as a socially appropriate response to a
   visitor. Directly addressed question trials are required.
5. A single successful Actions run does not establish multistep stability,
   learning, social realism, or security.
6. The current live Room has no deployed silence heartbeat, model-authored
   intention commit protocol, or atomic publication-and-consumption state.
7. Synthetic conversations are safe for exploratory trials but insufficient
   for human-likeness claims. Use blinded evaluations on multiple
   independently seeded episodes.

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
