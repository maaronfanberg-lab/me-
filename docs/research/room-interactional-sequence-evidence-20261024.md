# Research gate: interactional sequence evidence for the Room
**Date:** 2026-10-24. **Status:** staged research prototype; NOT a verified human-conversation model and NOT production-approved.

## Scope and provenance
The user's goal is not fewer repeated words. It is a conversational organization in which reusing a shared reference is appropriate when it does interactional work, and unproductive cycling becomes less likely because participants actually answer, acknowledge, repair, refuse, disagree, and develop their understanding.

**Oxford-specific work:** Oxford Research in Conversation Analysis (ORCA) is a research community that works from naturally occurring data. Oxford researcher Charlotte Albury and colleagues analyzed 226 recorded clinical exchanges: a clinician's pursuit after a patient's refusal often prolonged friction rather than accomplishing acceptance. A 2026 Oxford-linked systematic review across 43 studies reports several observed resources for communicating empathy, including minimal responses and witnessing. These are domain-specific findings, not rules for all ordinary conversation.

**Foundational scholarship, not necessarily University of Oxford:** Jack Sidnell's *Conversation Analysis* (Oxford Research Encyclopedia of Linguistics, 2016) reviews turn-taking, repair, action formation/ascription, and action sequencing. The publisher Oxford University Press must not be confused with the institutional origin of all cited research. Sacks, Schegloff & Jefferson (1974) analyzed locally administered turn allocation. Schegloff, Jefferson & Sacks (1977) documented a preference for self-initiated repair. Clark & Wilkes-Gibbs (1986) studied collaborative grounding. Brennan & Clark (1996) demonstrated partner-specific conceptual pacts, a direct reason *not* to forbid lexical repetition. Stivers et al. (2009) compared turn-taking in ten languages, with modest cultural timing differences and substantial common organization.

### Implementation precedents studied
- Traum's TRAINS grounding manager and Larsson & Traum's TRINDI toolkit distinguish dialogue acts, conversational obligations, and updates to a shared information state.
- IBM's Natural Conversation Framework / Alma Design System implements recipient design, minimization, and repair; IBM's 2024 study examines user-initiated repair on conversational interfaces.
- Morrison & Martens (2017) simulated multi-party initiative and turn-taking with beliefs, sentiment, personality, and relationships. Their expressive-range correlations are not a demonstration of natural human conversation.
- OpenDial uses probabilistic dialogue-state updates via a modular blackboard rather than treating every previous topic word as an independent observation.
- Liesenfeld & Dingemanse (2024) recommend *interactive probes* at the action-sequence level, rather than only sentence fluency or whole-chat engagement ratings.

## Ten-level research gate
1. **Observed symptom.** At ~25,860 Room cycles on 2026-10-23, the conversation repeatedly revolved around abstract "category classification trees," with little apparent response to specific participants' contributions. A reproducible snapshot of the **160 most recent feed messages** (`room/feed.json`, generated 2026-10-24T15:05:36Z) contains the whole word `category` in 151/160 (94%) and `trees` in 144/160 (90%). These percentages measure lexical saturation **only**, not semantic stagnation or failed interaction; transcript annotation is necessary.
2. **Foundational evidence.** An adjacency-pair first action makes some next actions conditionally relevant; a response or repair is a candidate for understanding, not proof of it. Clark's evidence about shared reference implies lexical reuse is sometimes cooperative.
3. **Current evidence.** Oxford's clinical studies show that response design matters more than reiterating an offer. IBM's 2024 repair results and 2024 action-level probing support engineering evaluations centered on the interaction.
4. **Natural behavior.** Prioritize recordings and their sequential analysis; do not use model-generated scripts as evidence of human norms. In text-only Room output, timing, overlap, gaze, and prosody cannot be inferred.
5. **Mechanism.** Treat a question as a *projection*; a later response as *candidate uptake*; a third-position acknowledgment/repair as evidence of how it was treated. Model does not infer agreement from word similarity, silence, or passage of time.
6. **Competing explanations.** Topic-memory circularity, an underpowered 1B generator, hidden prompt leakage, mandatory four-speaker production, and action-inappropriate model moves could each cause the observed failures. A new sequence frame alone may not change those mechanisms.
7. **Replication/limits.** Experimental conceptual pacts were demonstrated mainly in dyads and referential tasks, not longitudinal autonomous four-agent fiction. Regex recognition of questions and repairs has false positives/negatives. Oxford's clinician/patient refusal results cannot be directly generalized to peers.
8. **Context transfer.** Group conversation differs from dyads. Roles, recipient selection, pending bids, speaker abstention, inserted sequences, refusal, self-repair, and long-term history need testing independently. The first patch does not attempt human timing or silence.
9. **Implementation mapping.** A bounded action-sequence projection is computed from each character's **previously observed public encounters**, not from global history. It attaches to the pre-existing \`group_context\` on the expression input. Existing beliefs, relationships, personalities, and model transport are unchanged; no banned word lists, novelty target, or forced topic pivots are added. New fields are \`last_action\`, \`pending\`, \`recent_uptake\`, and an explicit uncertainty marker.
10. **Post-change validation requirement.** Run unit and old regressions, then compare against unchanged baseline via matched, replayable prompts and human action-sequence annotations. Production remains unchanged until causal effects are demonstrated.

## Important architectural discrepancies still unresolved
- The current Room orchestration schedules all four expression nodes every beat, using mandatory-speech flags and fixed per-beat contribution jobs. In ordinary interaction, a question to Sarah makes a response from Sarah relevant, not an obligation for Mara, Owen, and Jules all to speak. This requires a *separate, carefully tested turn-allocation change*, not a rushed rule limiting speakers to an arbitrary number.
- \`scripts/room_expression_quality_legacy.py\` rejects utterances with fewer than three lexical words (apart from some profanity). That can suppress minimal but sequentially appropriate continuers, refusals, acknowledgments, and repair initiations, even though conversation analysis documents their interactional functions. Merely whitelisting canned phrases would be a poor solution; future work should establish their relevance from the preceding move.
- Multiple layers still use direct instructions such as avoiding repeated phrasing and random "distinct contribution" jobs. The staged sequence context **does not yet remove those mechanisms**. To deliver the user's full objective, an A/B study should replace forced novelty with action-contingent plans and preserve repetition when it repairs meaning or refers efficiently to shared knowledge.
- Sequence parsing from \`?\` and a small set of repair cues is a conservative bootstrap. Genuine action ascription in naturally occurring talk depends on sequential position, epistemic context, stance, prosody and follow-up evidence. Misclassification must be measured with human annotation and not quietly promoted into a global "understood" truth state.

## Experiment and acceptance criteria
- **Offline test:** Question directed at Sarah makes a response relevant for Sarah but not Owen. A similarly worded unrelated contribution does not resolve it. Answering alone leaves understanding *unverified*; third-position clarification reopens repair; acknowledgment is evidence of reported uptake; refusal can be recognized without treating it as a malfunction. An absent listener acquires no unseen state.
- **Cross-component test:** Use the group's persisted observer-specific encounters and confirm the action projection survives \`model_context\` into the expression generator's compact payload. Run existing privacy, prompt-injection, dormancy, group-dynamics, topic, and publication tests.
- **Blind A/B:** Compare baseline and staged model using identical initial state, model version, seeds, and event scripts; sample multiple runs. Analyze at least 100 directed question/answer/repair sequences and 100 unrestricted action sequences before widening rollout. Annotation categories: conditional relevance, appropriate response, evidence of third-position understanding, repair initiation/completion, refusal acceptance, misattributed belief, and partner-specific continuity. Double-code a subset to assess agreement.
- **Success:** Better action-contingent responsiveness/repair with no regression in privacy, social continuity, or natural use of shared references. Word-type diversity is secondary, not an objective. Maintain ability to repeat intentionally for clarification, emphasis and humor.
- **Failure/rollback:** If question-addressing, observed repair, or epistemic attribution do not improve, or if output becomes more formulaic, revert the single-context-field integration. Examine the forced turn and prompt architecture before increasing filters.

## Sources (accessible publication/abstract URLs)
- ORCA: https://www.phc.ox.ac.uk/research/research-themes/health-behaviours-theme/orca-oxford-research-in-conversation-analysis
- Albury et al., patient refusals (2022): https://www.phc.ox.ac.uk/publications/1192600 ; DOI 10.1016/j.pec.2021.08.017
- Ta et al., empathy synthesis (2026): DOI 10.1186/s12913-026-14609-9
- Sidnell, Oxford Research Encyclopedia (2016): https://academic.oup.com/edited-volume/61882/chapter/547683169
- Sacks, Schegloff & Jefferson (1974): DOI 10.2307/412243
- Schegloff, Jefferson & Sacks (1977): DOI 10.2307/413107
- Clark & Wilkes-Gibbs (1986): DOI 10.1016/0010-0277(86)90010-7
- Brennan & Clark (1996): DOI 10.1037/0278-7393.22.6.1482
- Stivers et al. (2009): DOI 10.1073/pnas.0903616106
- Traum (1994): https://urresearch.rochester.edu/institutionalPublicationPublicView.action?institutionalItemVersionId=650
- Larsson & Traum (2000): DOI 10.1017/S1351324900002539
- IBM Alma (2020): https://research.ibm.com/publications/design-systems-for-conversational-ux
- Moore et al. (2024): https://research.ibm.com/publications/understanding-is-a-two-way-street-user-initiated-repair-on-agent-responses-and-hearing-in-conversational-interfaces
- Morrison & Martens (2017): https://arxiv.org/abs/1706.06987
- OpenDial: https://github.com/plison/opendial
- Liesenfeld & Dingemanse (2024): DOI 10.1177/17504813241267071

**Open questions:** Natural-language action ascription and turn allocation require corpus annotation and multiple rounds of refinement. This is a first verified mechanism candidate, not a claim that research is complete.
