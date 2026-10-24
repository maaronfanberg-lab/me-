# The Room: evidence-led conversational competence implementation plan
**Date:** 2026-10-24
**Status:** Thesis v1 for adversarial Claude review. Design only. No live changes authorized by this document.
**Branch:** research/conversation-sequence-evidence-20261024 / draft PR #313.

## Non-negotiable design contract
Enable four individual participants to use the ordinary organization of human interaction: speak when they have an interactional reason, respond when addressed, recognize when a contribution has or has not been understood, repair and pursue misunderstandings, negotiate common ground, make personal choices, and develop relationships over time.

**Do not optimize against repeated speech**, reward synonym changes, force arbitrary topic rotations, ban words, impose fixed speaker quotas, or write canned intimacy scripts. Reuse of prior wording and short utterances is valid when it contributes to repair, emphasis, reference, jokes, acknowledgment, disagreement or person-specific shared expressions. Guard against secret/prompt leakage and malformed output regardless of speech action.

The Room is text-only and cannot directly reproduce human timing, prosody, gaze, or overlap. Rules proposed below are engineering hypotheses inspired by research, not claims of universal human psychology.

## Baseline / observed root causes to test
- Published October 24, 2026 Room sample: 151/160 recent messages include "category" and 144/160 include "trees". These are lexical symptoms only.
- Production \`.github/workflows/sarah-society.yml\` invokes all four expression nodes (IDs 2,5,8,11), then \`room_private_commit.py\` publishes each surviving expression. \`mandatory_speech\` defaults true. Round-robin with rejection is not turn allocation.
- \`room_engine_v5_core.recurrent\` inserts \`conversation_job\`, "Distinct contribution", forced breakout subjects, and topic labels.
- \`room_private_model_autonomy_legacy.run\` includes word-level "Avoid copying recent speech" and minimum-words/retry checks. Some appropriate "No", "Why?", and "Right" turns can be discarded.
- \`room_topic_bounded.update_topic\`, \`room_private_commit.clean_terms\` and \`room_private_model._sanitize_expression\` can treat model/system-carried topic terms as new conversational evidence; this suspected self-feedback requires replay tests.
- Prototype \`room_interaction_sequence.interaction_frame\` from PR #313 is observational, but simplistic \`?\` and \`move_type\` heuristics, assumes a response when there is merely a directed next utterance, and does not yet drive the floor.

## Research and implementation precedents
Read \`docs/research/room-implementation-precedents-20261024.md\` and \`docs/research/room-interactional-sequence-evidence-20261024.md\` first. Prioritize Nonomura & Mori 2025 multi-agent turn allocation; Sacks/Schegloff/Jefferson turn-taking, sequences and repair; TRINDI dialogue information state; AutoGen's separate speaker selector; OpenDial probabilistic evidence; IBM/OpenDialog repair; Stanford Generative Agents provenance-linked episodic retrieval; Brennan & Clark conceptual pacts; conversation sequence-level evaluation.

## Phase 0. Baselines, corpus, safety envelope
1. Capture an immutable versioned snapshot of code/config (excluding secrets), state, cognitive_state, participants, sample transcripts and timestamp; preserve original as a rollback target. Do not put private prompts or tokens in artifacts.
2. Build a deterministic offline *replay reader* for recorded public events, preserving IDs, order, speaker, recipient, topic episodes, sleep/wake and Allen input provenance. Do not publish or mutate production in replay.
3. Produce hand-coded action sequence labels on at least 100 directed + 100 open-group/action episodes, including counterexamples (rhetorical questions, multi-recipient invitations, refusal, one-word continuers, repairs, disagreement, strategic repetition, absence). Double-annotate a subset. Report coding disagreement and false positives.
4. Record baseline: ignored directed responses, true repair success, uptake evidence, erroneous assumed agreement, privacy events, CPU/latency/failure, short legitimate turns wrongly filtered, per-agent commitment consistency. Track lexical saturation only as a diagnostic.
**Gate P0:** reproducible replay, validated IDs and observer scope, pre-registered definitions and enough annotated examples. Fail if dataset leakage or missing provenance.

## Phase 1. Observation and sequential evidence (unmerged draft base)
1. \`room_interaction_sequence.py\`: convert regex-only classification into evidence-scored *candidate* action recognition (first/second/third pair parts; question, answer, refusal, repair, backchannel, disagreement, account, closing, unsolicited offer). Record original source message ID, speaker, possible recipients, sequence links, confidence and uncertainty. A question mark alone does not establish a question or unique addressee.
2. Per-listener \`room_group_dynamics\`: observe only messages the listener was awake for and genuinely received; do not backfill upon waking. Ledger is append-only facts of **what was said**, separate from inference about **what was meant**.
3. Separate observed utterance, interpreter hypothesis, other-person belief hypothesis, and person-specific negotiated referent. An agent's response is not proof of understanding. A later acknowledgment or effective joint referencing is defeasible evidence, not absolute truth.
4. Evidence cannot be self-supporting: any summarized belief or "topic" reference must point to underlying independent utterances; avoid recycling topic-scaffold labels as novel input.
5. Bound context and record recency/identity without silently expiring live unanswered questions. Compress only with evidence links.
**Gate P1:** offline fixture tests for source attribution, pronoun/address ambiguity, rhetorical questions, unresolved bids, third-position repair, negotiated reference and observer privacy. Human-coded precision/recall reported with slices; uncertain cases abstain rather than invent understanding. No live behavior changes.

## Phase 2. Speaker selection before expression generation
1. Introduce \`room_floor.py\` as a pure, versioned *turn-opportunity* selector. It reads latest observed action, candidate recipients, commitments, genuine social motivation, individual readiness, relationship state and other agents' private bids. Returns an opportunity to answer/decline/repair, volunteer, prior speaker continue, or **no one**. It does not force a person to comply, and never decides next words.
2. Distinguish **one directed recipient**, multiple recipients/group question, unsolicited participation, one person talking twice, quiet after completion, and resumption after silence. Design deterministic tie-breaks for replay but no forced cycling or fairness quotas; track starvation as a safety metric, not an overriding conversational mechanism.
3. Stage a pure decision step **after sense and deliberation but before expression**; turn selection cannot happen only at publication (wasted models, wrong shared context, inconsistent outcomes).
4. For each beat, generate speech only for the selected participant; other minds may perceive and silently update only what they actually hear. Ensure code can express no-speech without losing live-state health or causing watchdog restart.
5. Selectable implementation runs behind \`ROOM_ACTION_FLOOR_V1\` default off, with deterministic shadow mode comparison. Existing path remains untouched until tests pass.
**Gate P2:** 50+ directed/group/refusal/multi-party/silent counterfactuals pass; addressed speaker gets opportunity; refusal and silence remain possible; a speaker may speak twice; sleep/wake safe. No false "dead runner" detection during genuine silence; relay and acknowledgement semantics correct.

## Phase 3. Intent realization and appropriate short utterances
1. \`room_engine_v5_core.recurrent\` separates candidate action plan from expression. Remove "Distinct contribution" role lottery and mandatory speech only in experimental path; do not just replace it with "Never repeat" instructions.
2. \`room_private_model_autonomy_legacy.run\`: realization input is compact: selected character, current action and interlocutor, 1-3 source-quoted utterances, own perspective, negotiated reference and uncertainty. Model chooses phrasing; may use earlier words if interactionally appropriate. Reject only privacy/malformed/unsupported invented shared facts.
3. Rework \`room_expression_quality_legacy\` and \`room_private_commit.validate_public_expression\`: minimal utterance allowed when doing evident appropriate action; no global min word count or lexical novelty score as a test of social value. Keep leakage, output schema, abuse/malformed constraints and quarantine *of invalid outputs*.
4. Human-labeled tests distinguish "Right" as acknowledgment, "Right?" as repair/incredulity, empty agreement, intentionally repeated term, and nonsense loops. An actually repeated phrase may be socially valid. If the tiny model cannot realize a given action, retry only with **new relevant evidence**, reduce abstention, or allow silence, rather than resampling contaminated context 9 times.
**Gate P3:** a sample of no fewer than 100 action/utterance pairs judged blind for action appropriateness and faithfulness; allow short utterances; no identity leakage, no synthetic generic empathy; do not accept reduced speech as sole success.

## Phase 4. Grounding, conceptual pacts and partner-specific memory
1. Per-person, *not global*, shared-reference pacts with observed evidence. Acknowledged references can be abbreviated; failed references trigger localized repair from the originating utterance.
2. Conversation sequences track refused/answered/contested/pending/abandoned/repaired as **actions**, not inferred correctness. Never turn a person's hypothesis into other persons' accepted fact automatically.
3. Retrieve from personal witnessed events ranked by current social action, intended partner, open commitments and referenced entities, not from repeated topic keywords. Reflections must link sources; static private-self seeds are descriptions, not reusable canned speech.
4. Preserve distinct personality and interpersonal styles; no hard-coded dialogue tone or affection. Revisit commitments and disagreements when socially relevant.
**Gate P4:** referential puzzle, misunderstanding, third-position correction, longitudinal remembered disagreement and per-character contradictory beliefs tested across save/load. A false belief must not contaminate other agents. Consent/refusal preserved.

## Phase 5. Persistence, runtime integration, reliability
1. Version separate action state; idempotent migrations from old \`room/state.json\` and \`room/cognitive_state.json\`; no clearing historic identities, relationships or legitimate messages.
2. Engine and workflow: run four perceptions (or existing process nodes) but only the selected expression; adjust \`bus2\` and \`room_private_commit.private_commit\` to accept optional zero or one expression; explicitly differentiate \`intentional_silence\`, \`no_valid_expression\` and infrastructure failure.
3. Pub/sub: atomic commit of message, sequence ledger, private listener updates and associated metadata; retry/rebase must not emit duplicate messages or silently lose Allen messages. Preserve active GitHub job, relay freshness, watchdog semantics, 429 retry, local-model fallback. Examine separate topic and relay paths to avoid accidental restarts.
4. Feature flag off by default. Dry-run/shadow, then canary copy with separate state + feed. No modifications to production state until go/no-go.
**Gate P5:** fault-injection for wrong addressee, concurrent git push conflict, model timeout, missing prompt, invalid structured output, all silent, 429, no network relay, duplicate event delivery, sleeping participant, Allen input ACK and restart. Verify no loss, corruption, double reply or runaway retries. Rollback restores old code path without deleting newly observed user information.

## Phase 6. Controlled evaluation and promotion
- A = current Room with same initial state/events; B1 = P1+P2 floor; B2 = +P3 action-realization; B3 = +P4 memory/grounding. Clone state and preserve parallel seeds; use >=3 paired runs per arm with multiple original contexts and held-out non-category conversations.
- Primary metrics: directed-answer appropriateness, conditional relevance, voluntary repair after misunderstanding, refusal acknowledgment, epistemic accuracy/common-ground evidence, relevance of memory callbacks, relationship continuity and diversity of actions/personality. Human double-coded excerpts with source IDs; blinded mixed-model evaluations secondary.
- Secondary metrics: semantically empty loops, lexical concentration, proportion silent, latency, tokens, cost, crashes. A lower repetition rate is *neither necessary nor sufficient*.
- Promotion requires preregistered relative improvement in primary action-relevance and repair without clinically/socially important regressions in truthful attribution, privacy, continuity, spontaneity or liveness; confidence intervals and power feasibility noted. If no measurable improvement, keep control.
- Canary rollout with rollback: deploy behind default-off toggle after branch reviews, test replay and independent CI. Observe live published turns before widening. Stop if misattribution, unanswered direct questions, persona leakage or watchdog churn rises.

## Crosscutting threat-model and bug gates
- **No hidden prompts/secrets** in branch notes, Claude inbox or outbox.
- Do not import third-party dialogue-system code without verifying license and dependencies; prefer reimplementing isolated mechanisms.
- Require adversarial red-team against prompt-injection spoken by a Room character/Allen, contaminated legacy state, and false interpersonal memories.
- Disable recovery loops that appear to fix phrasing by instructing characters to vary words; keep *privacy and integrity* quarantines.
- Pin and validate algorithms by source IDs, versioned state migrations, counterfactual replay and reversible rollout.
- Stop dialectical review when two consecutive adversarial reviews find no **new blocking defects**, not when someone merely says "bug-free." If defects emerge, revise and repeat. Code cannot be guaranteed bug-free by discussion.

## Review questions for Claude
1. Identify technical contradictions in the above ordering, particularly floor timing versus four-node recurrent stage, committed state and liveness.
2. Offer concrete failure traces and minimal fixes, not generic advice. Rank blockers by severity; tests that falsify each.
3. Challenge whether the plan covertly reintroduces lexical anti-repetition or artificial topic drift.
4. Consider low-confidence action parsing, generative 1B capability, ambiguous address, refusal, deliberate silence, individual observer scope.
5. State whether any phase should be split or re-ordered and list risks unaddressed by the 10-level research gate.

## Review log
- Thesis v1 authored for review. Claude antithesis pending. No production modifications.
