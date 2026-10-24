# The Room human-conversation architecture: reviewed implementation plan
**Date:** 2026-10-24. **Canonical version:** synthesis v2, following adversarial Claude review 1.
**Status:** planning only; no changes to production Room behavior. Draft PR #313 is unmerged. Original v1 remains retrievable in git commit de527812b1a03f36823d4537052b1576ff29bf54.

## Design objective and non-negotiable rules
Sarah, Mara, Jules and Owen should respond to one another through **socially meaningful action**: who is addressed, what is left unresolved, what the participants understood or contested, what each remembers, and whether a participant wants to speak. Neither lexical diversity nor fewer repeated phrases is a success criterion. Repetition for repair, reference, emphasis, rhythm, intimacy, teasing, or remembered commitments is legitimate. No canned social scripts, mandatory novelty, arbitrary topic changes, fixed floor quotas, or global proscription on short speech. Preserve character individuality, intentional silence and appropriate consecutive turns.

Text-only simulations lack human prosody/gaze/timing and cannot directly reproduce the full ecology of naturally occurring conversation. Contextual action inference is always an estimate, not privileged access to intent.

## Evidence and implementation basis
See the adjacent implementation precedents and conversation-analysis notes. Main transfer sources: Nonomura & Mori (2025) 4-agent turn choice from first-pair parts and self-selection; Sacks/Schegloff/Jefferson turn allocation and repair; TRINDI/GoDiS information-state updates; Microsoft's AutoGen separation of speaker selection and generation; OpenDial uncertain information states; IBM and OpenDialog repair; Stanford Generative Agents source-linked memory; Brennan & Clark shared conceptual pacts. Transfer from dyadic task dialogue and a 4-agent murder mystery to our unscripted Room remains a hypothesis.

**Observed baseline:** 2026-10-24 published feed sample n=160, words "category" in 151 and "trees" in 144. This is not a formal quality score. Production orchestrator .github/workflows/sarah-society.yml generates expressions for nodes 2/5/8/11 each beat; others are involved in perception/recurrent work. \`scripts/room_private_commit.py\` publishes each valid expression. If all fail, commit returns without updating state. Room Pulse can treat a stale state as a failed process after 900s. \`room_engine_v5_core.recurrent\` inserts "Distinct contribution" jobs and topic breakout; \`room_private_model_autonomy_legacy.run\` and \`room_expression_quality_legacy\` apply short-speech, echo/novelty and structural tests. Topic terms are blended with a speaker's purported semantic evidence; suspected circularity must be tested rather than assumed. Draft \`room_interaction_sequence.py\` is a heuristic observer-scoped annotation, not robust turn allocation.

## Architecture interfaces (to be frozen by contract tests)
- **ObservedTurn**: immutable \`message_id, beat_id, speaker, public_text, timestamp, recipient_claim, observed_by[]\`; private prompt and hidden reasoning never persisted in public files.
- **ActionHypothesis**: \`source_message_id, interpreter, action_candidates[], addressees[], confidence, evidence_span, provenance, unknown\`. Never treat model self-declared \`move_type\` or "?" alone as truth.
- **SequenceLedger**: \`first_pair_id, potential_recipients, candidate_next_action, candidate_second_pair_id, third_position_id, status[open|response_observed|repair_requested|accepted_for_now|contested|withdrawn|unknown], supporting_ids[]\`.
- **PerListenerState**: \`seen_message_ids\`, own pending goals, belief hypotheses with source IDs, relationship-specific conceptual reference pacts. An observer may be uncertain; sleeping people acquire nothing they did not see.
- **TurnOpportunity**: \`eligible_speakers[], reason_source_ids[], action_affordances[], confidence, allow_silence, allow_current_speaker_continue\`. Output is *an opportunity*, never an obligation to answer.
- **BeatResult**: \`beat_id, public_message_ids[], awake_participants[], reason[spoken|voluntary_silence|expression_quarantined|infrastructure_failure], complete\`. Version, idempotency and timestamp separated; never infer public speech from heartbeat.

All new fields versioned and behind a **default-off** feature gate \`ROOM_ACTION_FLOOR_V1\`. No new external dependencies unless reviewed for license/size and justified against the existing ~1B model.

## Canonical phased implementation and gates

### Phase 0A: non-mutating baseline and safe research harness
1. Immutable production snapshot of nonsecret source revision and dated, separately versioned state/transcript/config. Preserve sleep/wake, Allen messages, event IDs and model version. Production remains unchanged. Experimental runner must explicitly refuse production GitHub write tokens, relay credentials and public endpoints; assert \`ROOM_EXPERIMENTAL=1\` and sandbox data roots.
2. Build event replay, observer-specific projections and a differential-test harness. Label at least 100 directed and 100 group/unsolicited action sequences, with a held-out difficult corpus: rhetorical questions, two people addressed, repair echoes, refusals, one-word continuers, conflicting beliefs, shared humor, misheard implications, repeated refrains, third-position correction. Double-code part of sample, resolve/record disagreements rather than count uncertainty as errors.
3. Inventory **every** expression rejection predicate across model/autonomy/prompt/quality/commit layers, its rationale, and the failing action it can suppress. Document whether privacy/structural gate vs "freshness" gate.
4. Pre-register primary metrics: recipient-appropriate response, repair initiation and observable resolution, successful sequential closure, acknowledging refusals, mistaken attribution/false common ground, callbacks to genuine shared reference, individuality/relationship continuity, and participant-initiated topic movement. Track token lexical saturation only as a **secondary diagnostic**. Record baseline fault rate, timeouts, runner cost.
**Gate A:** corpus/replay reproducible from immutable IDs, reviewer agreement documented, no production writes possible, every known veto inventoried.

### Phase 0B: generation capability and semantic input ablations
1. On a fixed testbed of at least 100 annotated actions and three repetitions/seeds, test local Llama 3.2 1B Q4 ability to realize just *one* action and address a person, with grounded 1-3 message excerpts; freeze model/hash/temperature. Include baseline with topic labels versus topic labels masked; also test whether the generated text is **faithful to source**, not merely novel.
2. Test "Yes", "No", "Trees?", short echo repair, a hostile refusal, a careful answer and intentional reuse of shared reference. Check both blind-rated speech quality and JSON/latency. Fallback Qwen 0.5B tested separately, never silently mixed into A/B.
3. Offline counterfactual for circularity: derive topic terms only from speaker-authored text, versus scaffold-carried labels, and observe influence on subsequent prompt/generation. Do not delete legitimate shared topic words or force new subjects.
**Gate B:** capacity findings recorded. If model fails, prioritize bounded action-conditioned inputs, evidence simplification, or separately evaluated alternate model; **do not substitute canned phrases**. Pre-register an achievable minimum (candidate ≥80% action appropriateness on held-out unambiguous turns, with uncertainty intervals) and test cost envelope before heavier work.

### Phase 1: silent-beat safety, publication integrity, migrations (before voluntary silence)
1. Design an explicit distinction between an **empty but healthy conversational beat** and an infrastructure crash. \`last_healthy_beat_at\` and \`last_public_message_at\` are separate; Room Pulse and supervisor must use the correct signal. A silent beat advances private, healthy clock state, not the public transcript or conversation topic as if speech happened.
2. Ledger each completed beat with source IDs, reason codes, explicit awake/observed scope, and idempotency by stable beat ID on retry. Semantically equivalent idempotent replay (exclude run timestamp and SHA differences), not unrealistic byte-identical timestamps.
3. Commit transcript, state, topic and per-observer memory together as one **Git commit** after in-process staging. Audit multi-file write/rename boundaries before invoking git. A successful git push precedes relay/ACK; on failed push discard local unpublished state. Relay is at-least-once and must use dedupe IDs; Allen input is acknowledged only after durable acceptance and not lost when relay fails. Explicitly audit existing \`publish_relay\` best-effort and \`ack_allen_turns\` ordering.
4. Backwards-compatible versioned migration from existing \`room/state.json\`, \`room/cognitive_state.json\` and group-dynamics. Nothing erases history, personality, source identity, legitimate words, or partner-specific memory.
5. Stop silent-loop watchdog churn without requiring a character to speak. Keep external events / self-initiation possible but no forced speech. Avoid heartbeat-only Git write storms with a bounded healthy-state cadence compatible with actual watchdog tolerance.
**Gate C:** faults injected before/after each local write, before/after push, around relay and ACK, non-fast-forward push, duplicate beat ID, Allen input, model timeout, prolonged 100% silence past 900s, sleeping return. No duplicate public IDs, no lost Allen messages, no fabricated turn, no extra restart on healthy silence, no corrupted relationships or wrong retroactive knowledge.

### Phase 2: action-aware validation and prompt decoupling in shadow (still fixed production behavior)
1. In experimental path remove \`mandatory_speech\`, random "Distinct contribution" role lottery, retry instructions demanding new *wording*, and deterministic topic breakout, **but only after P1 heartbeat and safe no-speech results exist**. Do not remove privacy, content-integrity, source-provenance, malformed-output or structural guards.
2. Validation uses the selected **evidence-linked candidate action**, not the generated self-reported move (which may be wrong). A repeated question fragment may validly initiate repair. A repeated nonsense loop may still be invalid as incoherent without prohibiting a repeated word.
3. Test complete path from expression to \`validate_public_expression\`, \`room_expression_quality\` and publication quarantine; one-word ACK/repair, repeated referent or theatrical refrain pass when contextually valid; prompt leakage, gibberish and fabricated confidences still fail.
4. Stop feedback-loop topic injection becoming "independent" evidence by annotating \`speaker_utterance_terms\` separately from \`system_topic_in_scope\`. Do NOT judge topic progress by token count or automatically pivot topics.
**Gate D:** every staged legitimate-repeat fixture passes *the actual full validation chain*, all structural/privacy negative controls still blocked, no instruction makes novelty a speech goal; offline state replay demonstrates provenance separation.

### Phase 3: probabilistic/abstaining action recognition in observer-local shadow
1. Extend \`room_interaction_sequence\` with candidate action types, confidence/unknown, addressee ambiguity, evidence links and third-position uptake; \`?\` and generated \`move_type\` alone insufficient.
2. Label each event based only on what listener personally observed and previously knew. A respondent saying "Right" is not automatically agreeing; sequence position and later uptake matter. Public speech is evidence of speaking, not proof of intent or belief.
3. Human calibration on held-out cases; uncertain classifications lead to *conservative opportunity*, not coercion and not fabricated common ground.
**Gate E:** report confusion matrices, false positive/negative by action (especially question/refusal/repair/third-position), inter-rater agreement; evaluate abstention utility, not arbitrary guessed precision. Proposed initial floor readiness bar: on unambiguous directed turns, ≥90% correct recipient candidate, ≤2% false certainty on known ambiguous cases; revisit numbers if corpus renders them infeasible. Reliability/observer privacy and standalone No/Why? tested.

### Phase 4: first-pair / self-selection floor arbitration and real one-voice expression
1. Add pure \`room_floor.select_opportunities\`: addressed person receives a *relevant opportunity* (not compelled response); otherwise characters may self-select from personal goals/readiness and shared interaction. Group invitations allow several candidates, none or self-resumption. Tie-break deterministic for replay but not round-robin in disguise.
2. In experimental engine/orchestrator, keep existing perception and private processes as needed, run **one selected expression node** *after arbitration* and before publication; avoid paying for all four generations and then dropping three. Unselected minds may update on observed published events only. Commit can handle exactly one or no speech; silent beat path from P1.
3. No hard "never two consecutive turns"; no forced question response; no fairness quota disguised as human rule. Monitor starvation and disproportionate silence, investigate misattributed floor opportunities.
4. Shadow compare floor choices against real human annotations *before* routing actual generation.
**Gate F:** 50+ counterfactuals, no incorrect addressee forced, proper handling of overlap/group address, direct refusal, a quiet beat, self continuation, interrupting with a socially relevant objection, and unseen sleeping-agent non-selection. Reliable runtime with no 900s stall during 20+ seeds with periods of silence.

### Phase 5: grounding, repair, mutual understanding and relationships
1. A reply is **candidate uptake**. One participant's acknowledgement or continued successful reference gives provisional person-specific common ground, not globally verified truth. Update per-person \`what_I_believe\`, \`what_I_think_other_believes\` and source-linked partner pacts separately.
2. Misunderstanding prompts retrieval of the *original trouble-source utterance*, not a new topic. Person may self-repair, other-initiate repair, refuse repair or abandon; all permitted, with consequences for relationship.
3. Retrieval from the character's actual observations, partner history, unresolved bids and own agenda; never mine summary claims to create fresh independent "facts". Protect absent agents and avoid frozen \`private_self.what_i_want\` echoes leaking into public speech.
4. Allow topics to move by actual activity boundaries, side sequences, tangents, and volunteered interest rather than novelty timers.
**Gate G:** source-traced multi-session tests across save/reload, witnessed vs missed event, retraction, partner-specific naming pact, playful repetition, third-position repair and contrasting beliefs. No mistaken global consensus.

### Phase 6: controlled offline A/B, canary, rollback
- Treatment B1 = Phase 4 floor with observer-local action state. Treatment B2 = + move-aware realization/validation. Treatment B3 = + person-specific repair/memory. Controls share the same model/hash, event scripts, initial snapshot and random seeds (≥3 paired runs per arm, multiple starting conditions). Experimental branches cannot post to production.
- Primary outcomes: blinded human-coded action appropriateness, directed bids honored or legitimately declined, repair, refusal handling, epistemic humility, intimacy/belief trajectory consistency and natural topic movements. Annotators blind to arm, reason codes separately audited. Lexical repetition rate not a target.
- Promotion: pre-registered minimum improvement in action relevance/repair with no regression beyond specified tolerances in source truth, identity privacy, liveness, meaningful silence, short response or personality. Include uncertainty intervals and sample size/power caveat.
- Feature flag defaults off and is reversible; restore previous runtime code after rollback while preserving new public user input and acknowledged events through migration. No wholesale conversation deletion. Canary copy first, then staged deployment after passing tests; manual stop conditions on wrong recipient, loss/duplication, false common ground or watchdog churn.
- "Bug-free" is not verifiable by conversation. Release criterion is **zero known blocking defects** in a named threat/fault matrix and passing independently repeatable tests. Any new blocker reopens the review.

## Continuous review and failure matrix
| ID | Threat / trace | Required test |
|----|----------------|---------------|
| L1 | all silent, no state update, watchdog restarts | >900s simulated silence, 3+ beats, healthy state progress, no new public turn |
| V1 | "Trees?" rejected as echo and too short | full validator sequence accepts real repair, rejects prompt leaks |
| A1 | rhetorical '?' picks wrong recipient | action hypothesis unknown, no forced reply |
| M1 | absent Jules receives inferred common ground | observer-specific source link, Jules has no record |
| P1 | crash between staged files and Git push | no publicly visible partial state, restart replays safely |
| P2 | push race, duplicate beat / relay/ACK | idempotent messages and durable input acknowledgment |
| G1 | topic scaffold feeds its own terms as speaker evidence | provenance ablation + offline replay |
| C1 | 1B cannot reliably realize "refuse/repair" | model-pinned action fidelity eval, alternate bounded path |
| S1 | 100% silence suppresses all interaction forever | silent health pass, external/new voluntary invitation still possible |
| E1 | improved vocabulary variety but worse coherence | reject by blind action-relevance primary measure |
| X1 | action classifier gamed by generated move_type | validate against utterance and source, conservative abstention |
| R1 | looped reflection propagates unsupported belief | each inference linked to raw source IDs |
| N1 | high false positives from natural repeat checks | legal echo/refusal/repair and negative gibberish in same fixture |

## Explicit assessment of Claude antithesis round 1
**Verified response:** bridge/outbox/room-human-conversation-dialectic-r1-20261024.json, Claude Sonnet 5.5, ok=true.
**Accepted:** silent-beat watchdog contradiction, multiple expression vetoes, brittle action interpretation, weak low-capacity model and topic contamination, need to move liveness/recovery before voluntary silence. Accepted addition of rollback, fault-injection and source-linked observer state.
**Qualified:** Claude posited an externally published *partial* beat after c.record. In present flow c.record is in memory until files saved, then a later Git commit/push publishes as a unit. The real risks are crashes between local saves, non-fast-forward pushes, external relay/ACK, and replaying inputs; test those exact boundaries instead. Byte-identical outcome is not a sensible invariant when timestamps/hashes vary; compare canonical semantic state. Do not use arbitrary "bounded silence rate" as a force-speech rule.
**Rejected:** fallback to fixed canned action templates is inconsistent with user objective; choose evidence simplification or independently evaluated model capacity. Do not require output divergence under topic masking as a success measure; provenance and action/content appropriateness matter.
**Disposition:** all five severity areas have design mitigations, but *tests have not run*. No claim of production bug-free status.

## Thesis / antithesis / synthesis log
- Thesis v1 at commit de527812b1a03f36823d4537052b1576ff29bf54.
- Antithesis r1: verified Claude consulted 2026-10-24, identified five blocking failure modes.
- Synthesis v2: this document. **Claude second review pending.** Continue until two consecutive focused reviews yield no *new* credible blocking defect, or document unresolved blockers honestly; do not claim infinite proof.
