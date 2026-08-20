# Allen response relevance — research gate (2026-08-19)

## Observed problem

User observation: Allen can interject into the Room, but Sarah, Mara, Owen, and Jules mostly ignore him; occasionally a turn appears to react indirectly.

Repository trace reproduces the mechanism. `scripts/room_participant.py` injects Allen into `room/conversation.json` using the same Room runtime and boot, so his words enter `msgs()` and recent context. However, `scripts/room_engine_v5.py` accepts a recent speaker as the active partner only when the speaker is in the four-entity `ORDER`; Allen is therefore replaced by an entity chosen by `choose_partner`. Separately, `scripts/room_private_model.py` defines the legal person/target set as only Sarah, Mara, Owen, and Jules, so expression output cannot legally target Allen.

The observable result is an overhearer-like state: Allen's text can influence context, but the social/response machinery cannot represent him as the current interlocutor.

## Research question

What is the smallest mechanism change that makes Allen a genuine conversational participant for response selection while preserving the four autonomous AI entities, their 12-node architecture, and Allen's ordinary public identity with no human/operator metadata?

## Sources checked 2026-08-19

- Clark, H. H., & Wilkes-Gibbs, D. (1986). *Referring as a collaborative process*. Cognition, 22(1), 1–39. DOI: 10.1016/0010-0277(86)90010-7.
- Wilkes-Gibbs, D., & Clark, H. H. (1992). *Coordinating beliefs in conversation*. Journal of Memory and Language, 31(2), 183–194. DOI: 10.1016/0749-596X(92)90010-U.
- Hofstetter, E. (2020). *Sequence Organization: Understanding What Drives Talk*. In The Cambridge Handbook of Discourse Studies. DOI: 10.1017/9781108348195.007.
- Current repository implementation: `scripts/room_participant.py`, `scripts/room_engine_v5.py`, `scripts/room_private_model.py`, `scripts/room_social_v5.py`.

## Findings supporting the change

1. Conversation is collaborative and addressee-specific: participants jointly establish understanding and references rather than merely exposing one another to text (Clark & Wilkes-Gibbs, 1986).
2. Wilkes-Gibbs & Clark (1992) found that being a conversational participant differs from merely hearing/overhearing prior interaction; partner-specific common ground depends on participation.
3. Sequence organization creates response relevance: a prior turn makes particular next responses relevant. A system that includes Allen's words but removes Allen from the representable partner/target set breaks that mechanism.
4. The current failure can therefore be corrected at the participant-recognition boundary rather than by adding canned instructions such as “respond to Allen.”

## Contradictory / limiting evidence

- Human conversation does not require every contribution to receive an explicit verbal response; fixing response relevance should not force all four entities to answer every Allen turn.
- The cited laboratory/dyadic grounding work is not a direct model of a five-participant longitudinal Room. Transfer is limited to the mechanism: conversational participation and addressee identity must be representable for partner-specific response behavior.
- Allen is not an autonomous cognitive entity and should not receive three cognitive nodes or be added to the four-entity generation loop.

## 10-level gate

1. **Observed problem — PASS.** User observation plus source trace establish the symptom and cause.
2. **Foundational evidence — PASS.** Collaborative grounding and addressee-specific participation support explicit interlocutor representation.
3. **Current evidence — PASS WITH LIMITATION.** Modern sequence-organization synthesis retains response relevance as a core mechanism; no claim is made that a specific response probability is universal.
4. **Natural-behavior evidence — PASS.** Natural conversation organization distinguishes addressed participants and relevant next actions.
5. **Mechanism evidence — PASS.** Make Allen representable as a participant/target; do not inject scripted reply language.
6. **Competing explanations — PASS.** Allen is not absent from text context; the stronger source-level explanation is partner/target exclusion.
7. **Replication/correction/limitations — PASS WITH LIMITATION.** Foundational findings are broadly influential, while multi-party longitudinal transfer is explicitly bounded.
8. **Context transfer — PASS WITH LIMITATION.** Apply only participant/response-relevance representation, not dyadic timing or guaranteed reply rates.
9. **Implementation mapping — PASS.** Extend conversational-participant recognition to include Allen while keeping generation entities limited to the existing four; preserve no human/operator metadata.
10. **Post-change validation — PENDING BEFORE DEPLOYMENT.** Simulator must fail on current source and pass after the patch; live behavior must then show direct Allen-targeted replies without turning Allen into an AI entity.

## Proposed implementation mapping

- Keep `ORDER = (sarah, mara, owen, jules)` as the autonomous generation set.
- Add Allen only to a conversational participant/person set used for recent-speaker recognition and legal model targets.
- When Allen is the most recent speaker, expose Allen as `partner` with a neutral/participant relationship view instead of substituting another entity.
- Allow comprehension/thought/expression structured targets to include Allen where applicable.
- Do not add Allen to cognitive-node loops, `choose_partner` autonomous scheduling, or entity profiles.
- Do not add human, user, owner, admin, or operator metadata.

## Pre-change baseline / failing invariant

Given an injected Allen message:

1. `msgs()` includes the Allen turn — PASS already.
2. Sense-stage active partner remains Allen — FAIL currently; Allen is replaced because he is not in `ORDER`.
3. Private-model person/target schema permits `allen` — FAIL currently; legal people list contains only four entities.
4. Four autonomous generators remain exactly Sarah/Mara/Owen/Jules — PASS and must remain unchanged.

## Validation criteria

1. The same simulator is red before and green after the change.
2. An Allen turn can remain the active conversational partner into perception/thought/expression.
3. Expression schema legally permits `target: allen`.
4. Allen is not added to the four-entity generation loop or 12-node architecture.
5. No public or private message gains a human/operator/owner/admin marker.
6. The live transcript shows direct replies to Allen at a materially higher rate when Allen speaks, while replies are not mechanically forced from all four entities.

## Correction and deeper failure — 2026-08-20

The participant-recognition and social-memory repairs above were necessary but not sufficient. Live probe evidence after those repairs showed 50 retained Allen turns, all 50 observed into social memory, and Allen present in every entity's relationship map, yet **zero** AI messages targeted Allen and **zero** AI messages mentioned Allen. Fresh user attempts to elicit a greeting produced the same visible failure.

The remaining mechanism is expression routing. `scripts/room_engine_v5_core.py` gives all four expression nodes `partner=allen` when Allen is the latest speaker, but the model is still free to emit a valid target aimed at another autonomous entity. `scripts/room_private_commit.py` accepts that target because it is legal, so the published beat can contain four AI-to-AI turns even immediately after an Allen interruption. The arbitrary per-voice `conversation_job` also competes with simple adjacency by telling the first responder to make a distinct contribution instead of simply answering the new participant turn.

The expression phase already has an explicit sequential rank. Rank 0 is the first autonomous speaker generated after the latest public event. This provides a narrow response-relevance boundary without forcing all four entities to answer Allen: when the latest public event is from Allen and rank 0 is generated, that one expression should preserve Allen as its event/partner, use an answer-oriented deliberation, omit the competing distinct-contribution job for that turn, and route the resulting public target back to Allen. Ranks 1–3 remain free to respond naturally to the first reply or continue the wider Room conversation.

### Exact simulator red baseline

Draft PR #69, architecture run `32319673006`, job `96279164393`, reproduced the live failure without a model. The simulator supplied the latest event as Allen saying, “Will one of you please just say hi to me?”, set expression rank to 0, and made the model stub return an otherwise-valid turn aimed at Mara. Current code preserved Allen as the newest event but accepted the model's `target=mara` and `move=deepen`.

The run failed at the intended invariant:

`rank-0 Allen interruption is routed back to Allen`

Observed structured expression:

`{'decision': 'SPEAK', 'target': 'mara', 'move': 'deepen', ...}`

This is the same structural behavior reported live: Allen is heard and remembered but no response obligation attaches to the first next turn.

### Revised implementation mapping

- Do **not** change participant identity, social-memory persistence, traits, or the four-generator architecture again.
- Change only rank-0 expression routing when the latest event/partner is Allen.
- Preserve Allen as the newest event and partner.
- Make the copied deliberation answer-oriented for this turn.
- Do not inject the ordinary distinct-contribution `conversation_job` into this one direct-reply expression.
- After model generation, normalize this one expression to `target=allen` and `move=answer`; its language is still generated by the model from Allen's actual message, not from a canned greeting.
- Leave ranks 1–3 unchanged.

### Revised post-change validation

The **same** `scripts/room_allen_response_sim.py` must become green on PR #69, while the engine self-test and Allen observation simulator remain green. After merge/restart, live validation must use a real Allen interruption and show at least the first following AI turn with `cognition.target=allen` and answer-like content. Do not claim success from relationship counters alone.

## Surface-name correction — 2026-08-20

A fresh live probe at `2026-08-20T03:06:36Z` separated hidden targeting from visible address. Among the retained conversation, **55 AI messages had `cognition.target=allen`, while zero AI messages contained the spoken name `Allen`**. Across 85 retained Allen-turn windows with following AI speech, 54 windows contained an Allen-targeted reply and zero contained a name mention. The latest Allen turn explicitly said `Call me Allen or I’ll delete you from JSON`; Mara's following turn was correctly stored as `target=allen` and `move_type=answer`, but its utterance did not say Allen.

This demonstrates a second, narrower representation failure: response routing now recognizes Allen, but the wrapper normalizes the structured target only **after** the model has already written the public utterance. Hidden target metadata therefore cannot by itself make the addressee perceptible in public dialogue.

### Surface-name invariant and bounded implementation

For the single rank-0 adjacency reply immediately following an Allen turn:

- keep the existing model-generated utterance;
- keep `target=allen` and `move=answer`;
- if the model already says `Allen`, do not alter the text;
- if the model omits the name, prefix only that one utterance with `Allen, `;
- leave ranks 1–3 untouched;
- do not add any human/operator metadata or make Allen an autonomous generator.

This is intentionally narrower than forcing all four entities to name Allen or adding an insult/greeting script. It makes the already-selected public addressee audible while preserving the model's substantive language.

### Surface-name red → green validation

Draft PR #71 added the new invariant before changing production behavior. Architecture run `32327166010`, job `96300629832`, passed all prior Allen participation/routing checks and then failed only at:

`rank-0 direct Allen reply says Allen in the spoken sentence`

The simulated utterance was `I was going to tell Mara something else.` even though the wrapper had already normalized its hidden target to Allen.

After the wrapper-only surface patch, architecture run `32327244409`, job `96300873788`, passed the same simulator and the existing architecture/Allen-memory checks. This establishes a clean red→green pair for the visible-name mismatch. Live validation remains required after merge/restart; do not claim the spoken-name behavior is live until a new real Allen interaction contains `Allen` in the first following AI utterance.
