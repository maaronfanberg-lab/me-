# The Room human-conversation architecture: reviewed implementation plan
**Date:** 2026-10-24. **Canonical version:** synthesis v3, after verified adversarial Claude reviews 1 and 2.
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

## Synthesis v3: typed outcomes, durable delivery, isolated evaluation and falsifiable gates

### A. Typed beat health: silence is not failure
A **valid decision of no speech** is \`chosen_silence\` and may advance the healthy-clock watermark. No selected speaker owing to genuine voluntary disinterest is also healthy, provided the floor itself completed. By contrast \`generation_failed\`, \`validation_failed\`, \`model_unavailable\`, missing expected model output, and \`infrastructure_failure\` are **unhealthy** and must raise fault counters; they never refresh the healthy-beat signal. An all-invalid set is a failure, not a social decision. The watchdog must inspect the persistent healthy timestamp **and** failure counters, not the public-message timestamp. Repeated failures or stale health trigger alert/restart using existing safe recovery; healthy silence does neither. Each observed outcome includes source, attempt and reason codes with no private prompts.

Because a Git commit per silent millisecond would itself be a bug, batch **non-public health/ledger updates** and persist no more frequently than a configured heartbeat interval (initial trial T=300 seconds, strictly below the 900-second watchdog threshold, with jitter/failure margin verified). Important change in outcome or a durable inbound event can flush sooner. On 1000 no-speech iterations, public transcript remains unchanged and Git commit count stays bounded by elapsed-time windows plus meaningful transitions. Archival beat diagnostics may be compacted with cumulative counters and source hashes. **Never coalesce or defer public speech/accepted user input merely to reduce heartbeat commits.**

### B. Publication and delivery state machine
**GitHub main is the authoritative transcript/state; Cloudflare relay is a recoverable mirror.** Verify this assumption against current consumer behavior and amend if the UI uses relay as sole recoverable source. An Allen input receipt ID, floor-decision ID and a stable committed sequence (derived from prior durable state, not \`GITHUB_RUN_ID\`) identify a beat. Define two separate idempotency domains: input consumption by Allen event ID and output publication by committed sequence + decision ID. Do **not** deduplicate all future replies that reference the same Allen utterance.

\`\`\`text
OBSERVED_INPUT -> PREPARED_DECISION -> STAGED_RESULT
    -> GIT_COMMITTED -> GIT_PUSH_CONFIRMED
    -> RELAY_PENDING -> RELAY_DELIVERED
    -> ACK_PENDING -> ACKED
\`\`\`

- Stage the selected **utterance bytes**, message IDs, exact observed input IDs and updated observer-state in local temporary files, then validate *all* files, rename/prepare the Git index, commit and push a complete snapshot. No remote publication until the full coherent Git commit exists. The job's local process may crash between file writes, but \`main\` must never publish the torn snapshot. Validate complete state before \`git add\`.
- On non-fast-forward push, check whether the stable decision is already present upstream. If yes, it is a no-op; if upstream state changed incompatibly, **discard the stale prepared result and replay once from newest durable state**. Do not rebase a stale utterance onto a new conversational state or regenerate differently under the *same* committed decision ID.
- Persist a relay-pending journal/outbox as part of the Git-published transaction. Relay delivery requires a real success acknowledgment and retry with a stable source-id dedupe; an unacknowledged mirror POST remains pending. Do not silently swallow relay 500s.
- Allen receipt ACK becomes eligible **after confirmed authoritative Git publication**, with \`processed_inbound_ids\` already persisted; ACK retries are safe and must not generate duplicate answers. A failed relay does not undo durable acceptance or invent a new answer, but it remains a visible delivery failure until healed. If end-user acknowledgment contract requires viewer delivery, explicitly alter the ACK gate; do not silently assume.
- Relay may be at-least-once; stable event IDs + merge/dedupe make the consumer effectively once-per-event. No claim of transactional exactly-once across GitHub and Cloudflare without real distributed transaction support.
- Byte-identical utterance across a resumed *same durable decision* is mandatory. Across intentionally invalidated/recomputed decisions after conflicting upstream events, changed speech is allowable **with a new decision ID**. Semantic state idempotence excludes timestamps, SHA and transport attempt metadata.

### C. Shadow and canary isolation
Experimental replay, shadow and A/B arms use **separate immutable fork roots**, private writable directories, separate state stores, separate logical event streams, and no production GitHub-write token, live relay URL, or Allen ACK endpoint. Shadow may read a *snapshot* but never mark a real participant as having witnessed a turn; shadow inference and metrics are stored only in its own namespace. A hash guard checks production state/config/feed before and after shadow; any difference fails the experiment. A production canary, if eventually approved, must use explicit separate namespace/relay and staged data migration; its outputs must not be simultaneously published as authentic Room speech.

### D. Measurable acceptance rubric, fixed before running models
- **Action appropriateness:** two independent blinded annotators score each emitted turn 0=inappropriate/unrelated, 1=partially relevant/uncertain, 2=appropriate to prior action (including principled refusal, repair, acknowledgment, or deliberate silence as applicable). Candidate criterion: ≥80% score 2 on 300 pinned-model outputs across ≥3 seeds; measure Wilson 95% lower bound and report by action/character (threshold calibrated and pre-registered from baseline before engineering promotion). Reviewer Cohen κ target ≥0.60 on categorical labels; disagreements adjudicated, not erased.
- **Recipient inference:** on held-out *unambiguous directed* instances, report correct-target precision **and coverage**. Initial gate: ≥90% point precision, ≥80% coverage, and Wilson 95% lower confidence bound on precision ≥0.85, with minimum n=100 actually predicted. On ambiguous turns, measure appropriate uncertainty/abstention separately and targeted false-certainty rate (suggested ≤10%).
- **Response, repair, continuity:** paired A/B with ≥100 directed response opportunities and ≥100 repair/refusal/unsolicited examples spanning ≥3 seeds and different topics. Require primary action-relevance improvement target ≥10 percentage points, confidence interval reported (if inconclusive, **do not deploy**). No >5 percentage point deterioration in independent blind ratings of continuity/grounding or intentional repetition allowance, and no rise in unsupported-fact attribution beyond control; uncertainty intervals must be included.
- **Integrity:** zero known privacy leakage, duplicate durable public IDs, lost accepted Allen receipts, successful full-pipeline phantom speech during \`chosen_silence\`, cross-arm writes, or sleeping-observer knowledge leaks in fault injection.
- **Reliability:** zero false watchdog restarts in a simulated >900-second chosen-silence scenario; simulated model-outage/invalid result is detectable as unhealthy within configured failure limits; 1000 silent iterations bounded Git commits by T; 5+ fault points through Git push/relay/ACK validated. Pin generator model per utterance and A/B arm: a fallback changes model condition and **invalidates** that sample for pinned analysis, it never silently counts.
- **Canary stop criteria:** immediately stop on a single confirmed identity/privacy leak, incorrect ACK/lost accepted message, duplicate public ID, cross-arm contamination or unrecoverable state migration; pause on repeated unhealthy outcomes above configured baseline or blinded-action quality deterioration more than 5 points. Monitoring of consecutive identical lines alerts review **without banning or automatically editing those lines**. Review whether they are genuine interactional repetitions.
- **Fail closed:** if the 1B model cannot pass the evidence-grounded action-realization gate, DO NOT activate speaker arbitration in live production. Test a better model, simpler evidence packet or reduce scope in a separate study. Do not mask weakness with canned text.

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

### Phase 1: silent-beat safety, publication/delivery integrity, migrations (before voluntary silence)
1. Implement the **typed beat outcome** health machine from section A, distinguishing voluntary \`chosen_silence\` from \`validation_failed\` or \`model_unavailable\`. Adjust both Room Pulse and Room supervisor to inspect health and failure semantics. Coalesce heartbeat-only writes to a tested cadence, not a Git commit on every quiet cycle.
2. Implement section B's **stable decision-ID and delivery state machine**: staged files and complete Git publication, rebase conflict conflict-check then replan if stale, \`processed_inbound_ids\`, relay-pending retry, source-ID dedupe, explicit Allen ACK after durable acceptance. Audit current mirror semantics before treating GitHub as authoritative for the user.
3. Version state migrations without losing identity, relationships, witnessed source IDs or legitimate history. Both old and new read paths tolerate unknown fields; no partial propagation to the control branch. Ensure \`ROOM_ACTION_FLOOR_V1\` off reproduces old public dialogue exactly in deterministic replay.
4. Fault-inject each local write, publish, Git race, relay 500 and crash before/after ACK. Test \`chosen_silence\` for 1000 cycles with simulated >900s elapsed and bounded commits; test all-invalid-model separately goes unhealthy; test sleep/wake and input ACK replay.
**Gate C:** typed liveness never masks a failed model, no false watchdog restarts during healthy silence, no split public/private state, no loss or duplication of accepted inbound events, no unacknowledged failed relay counted as delivered. Fail if production/control state changes during shadow.

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
**Gate F:** 50+ counterfactuals, no incorrect addressee forced, proper handling of overlap/group address, direct refusal, a quiet beat, self continuation, interrupting with a socially relevant objection, and unseen sleeping-agent non-selection. Keep unanswered questions in a linked open/contested/withdrawn state: lower *retrieval priority* after disengagement, never declare them answered from silence alone. Reliable runtime with no 900s stall during 20+ seeds with periods of silence.

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

## Explicit assessment of Claude antithesis round 2
**Verified response:** bridge/outbox/room-human-conversation-dialectic-r2-20261024.json, Claude Sonnet 5.5, ok=true. Identified critical new risks: distributed publish/relay/ACK transition semantics, healthy heartbeat masking actual model failure, heartbeat write storms, shadow/control contamination and indefensible numeric gates. Adopted all five as design corrections in sections A–D; also adopted observed-repeat monitoring without censorship and open-question persistence without forced speech. Qualified its 'permanent loss after relay failure' example: authoritative Git commit means source isn't lost, but mirror delivery may lag indefinitely unless persisted retry exists. Qualified all-silent commits: bound batching by health T, do not suppress durable input. Rejected introducing arbitrary topic-age expiry as 'solving' open questions; lower salience without asserting closure. Claude's B5 gates are candidates that must be calibrated and power-tested, not evidence of achieved reliability. **No code/tests yet run for these changes.**

## Explicit assessment of Claude antithesis round 1
**Verified response:** bridge/outbox/room-human-conversation-dialectic-r1-20261024.json, Claude Sonnet 5.5, ok=true.
**Accepted:** silent-beat watchdog contradiction, multiple expression vetoes, brittle action interpretation, weak low-capacity model and topic contamination, need to move liveness/recovery before voluntary silence. Accepted addition of rollback, fault-injection and source-linked observer state.
**Qualified:** Claude posited an externally published *partial* beat after c.record. In present flow c.record is in memory until files saved, then a later Git commit/push publishes as a unit. The real risks are crashes between local saves, non-fast-forward pushes, external relay/ACK, and replaying inputs; test those exact boundaries instead. Byte-identical outcome is not a sensible invariant when timestamps/hashes vary; compare canonical semantic state. Do not use arbitrary "bounded silence rate" as a force-speech rule.
**Rejected:** fallback to fixed canned action templates is inconsistent with user objective; choose evidence simplification or independently evaluated model capacity. Do not require output divergence under topic masking as a success measure; provenance and action/content appropriateness matter.
**Disposition:** all five severity areas have design mitigations, but *tests have not run*. No claim of production bug-free status.

## Thesis / antithesis / synthesis log
- Thesis v1 at commit de527812b1a03f36823d4537052b1576ff29bf54.
- Antithesis r1: verified Claude consulted 2026-10-24, identified five blocking failure modes.
- Synthesis v2 at commit a33b0e249b581ec85ed91d462d8758c819b44566.
- Antithesis r2: verified Claude consulted 2026-10-24; found additional delivery, heartbeat, shadow and evaluation blockers.
- Synthesis v3: this document; narrow round 3 pending on sections A–D. Continue until no new credible **blocking architecture flaw** is discovered in consecutive focused reviews or document limitations; review is not a proof of bug-free runtime.
