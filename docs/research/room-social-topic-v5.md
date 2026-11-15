# Room v5 — partner-specific relationships and topic depth

## Observed problem

The v4 engine guarantees four speakers per beat, but social development and topic development are too shallow. The legacy observer path increments a single familiarity value whenever another entity speaks, so mere exposure eventually collapses social distance. Topic continuation is bounded by a short discourse depth and repeatedly returns to a small generic starter/follow-up repertoire. This produces converging relationships, repeated wording, and broad-topic cycling.

Mandatory speech is a project constraint: Sarah, Mara, Owen, and Jules must each contribute exactly once per beat. v5 changes what their contributions do, not whether they speak.

## Research question

How should a four-person longitudinal conversation maintain mandatory participation while developing partner-specific relationships, deeper topic episodes, shared references, disagreement/repair, and non-uniform trust without treating exposure as trust?

## Evidence base

Starting evidence includes:

- Macy & Skvoretz (1998), *The Evolution of Trust and Cooperation Between Strangers: A Computational Model*, American Sociological Review 63:638–660 — social structure, optional interaction, local embeddedness, and diffusion of cooperation.
- Clark & Wilkes-Gibbs (1986), Cognition, doi:10.1016/0010-0277(86)90010-7 — collaborative grounding and reference.
- Schober & Clark (1989), Cognitive Psychology, *Understanding by addressees and overhearers* — direct addressees and overhearers do not acquire equivalent understanding merely by hearing the same words.
- Brennan & Clark (1996), JEP:LMC, doi:10.1037/0278-7393.22.6.1482 — partner-specific conceptual pacts and lexical entrainment.
- Sacks, Schegloff & Jefferson (1974) and Stivers et al. (2009), PNAS, doi:10.1073/pnas.0903616106 — turn organization and timing.
- Schegloff, Jefferson & Sacks (1977) — repair and preference for self-repair.
- Laurenceau, Barrett & Pietromonaco (1998), JPSP, doi:10.1037/0022-3514.74.5.1238 — disclosure, perceived responsiveness, and intimacy.
- Aron et al. (1997), PSPB, doi:10.1177/0146167297234003 — gradual reciprocal disclosure and closeness.
- Huang et al. (2017), JPSP, doi:10.1037/pspi0000097, considered together with later reanalysis/correction literature — follow-up questions can signal responsiveness but should not be equated mechanically with listening.
- llama.cpp official server documentation — one local model server supports local completion and parallel decode, allowing private node prompts to stay in runtime secrets rather than the public repository.

## Findings supporting the change

1. Exposure, direct participation, familiarity, trust, reciprocity, warmth, respect, and disclosure are distinct constructs and should not be represented by one automatically increasing scalar.
2. Relationship state should be directed and asymmetric. A→B need not equal B→A.
3. Overhearing may update exposure/knowledge, but direct relationship development should require interaction involving that pair.
4. Trust should update conservatively and only when an interaction contains interpersonal stake or informative reliability/repair evidence; ordinary chatter should not increase trust.
5. Shared references should accumulate per pair and become available for later callbacks.
6. Topic depth is better represented as an episode with a root, current facet, discovered facets, shared references, unresolved material, and novelty/saturation state than as a fixed discourse-depth counter.
7. Topic continuation should favor concrete facets already introduced; a generic follow-up question is not itself evidence of deeper conversation.
8. Stronger ties may influence targeting, but weak-tie novelty should remain possible so the group does not freeze into permanent dyads.
9. Mandatory four-person speech can coexist with differentiated interaction if each contribution has a distinct function: answer, deepen, compare, callback, disagreement, repair, support, or bridge.
10. Private prompts should be runtime-only. Public code should contain schemas, reducers, validation, and fallback behavior but not the private instruction text.

## Competing explanations and limitations

The repetitive v4 output was partly caused by deterministic canned language, not only by its social model. A better relationship model alone cannot guarantee natural language. The optional local Qwen2.5-0.5B model may also be too small to produce consistently strong multi-party conversation, so deterministic validation/fallback remains necessary.

Research on dyads does not transfer perfectly to four simultaneous entities. The Room's mandatory all-four speech is also unlike ordinary human conversation. v5 therefore treats the research as mechanism guidance rather than claiming the Room is a literal model of human interaction.

The numerical update rates in `room_social_v5.py` are conservative engineering heuristics chosen to make unsupported trust growth difficult. They are not empirical constants. Live validation already showed that the first linear update rates were too fast, so schema v3 replaced them with slower, diminishing updates and a one-time rescale based on observed direct-turn counts.

## 10-level gate

1. Observed problem: PASS — visible repetition plus source-level automatic familiarity growth.
2. Foundational evidence: PASS — conversation analysis, grounding, social exchange/trust literature.
3. Current evidence: PASS WITH ONGOING REVIEW — later experimental/network work and current runtime docs checked.
4. Natural-behavior evidence: PASS — addressee/overhearer, turn-taking, repair, disclosure and conversational grounding studies.
5. Mechanism evidence: PASS — state separation, directed history, grounding, topic episodes, repair/callback mechanisms.
6. Competing explanations: PASS — language-generation limitations explicitly retained as a separate cause.
7. Replication/correction/limitations: PASS WITH CAUTION — question-asking reanalysis/correction and context limits noted.
8. Context transfer: PASS WITH CAUTION — four-person mandatory speech differs from studied dyads; live validation is required.
9. Implementation mapping: PASS — implemented in `room_social_v5.py`, `room_engine_v5.py`, `room_private_model.py`, and the Room workflow.
10. Post-change validation: PASS FOR DETERMINISTIC V5 CORE; PRIVATE-PROMPT MODE PENDING SECRET ACTIVATION.

## Implementation mapping

- Nodes 0/3/6/9: social perception / grounding role. Optional private prompt is supplied only at runtime.
- Nodes 1/4/7/10: private topic/relationship deliberation role. Optional private prompt is supplied only at runtime.
- Nodes 2/5/8/11: expression role. Optional private prompt is supplied only at runtime.
- Private cognition is sequential: perception → deliberation → expression.
- All 12 nodes remain active; all four entities remain mandatory public contributors per beat.
- Relationship reducer is deterministic. The model does not directly set trust numbers.
- Directed relationship dimensions: exposure, direct familiarity, trust, predictability, reciprocity, warmth, respect, disclosure depth, tension, direct-turn count, repair attempts/successes, and shared references.
- Legacy `familiarity` is retained only for migration/audit and is not converted into high trust.
- Topic schema v3 assigns explicit semantic roots/facets and only accepts topic terms from messages belonging to the current episode ID.
- Topic episodes persist across beats and move through unvisited facets before bridging to a new topic.
- Exact/near-exact repeated text is penalized by novelty scoring in deterministic fallback generation.
- Prompt-leak markers and long verbatim overlap with the node's private prompt are rejected before local-model output is accepted.

## Privacy architecture

The public repository contains no private node prompt text. The workflow references three encrypted GitHub Actions secret names: `ROOM_PROMPT_PERCEPTION`, `ROOM_PROMPT_DELIBERATION`, and `ROOM_PROMPT_EXPRESSION`.

At runtime:

1. the parent workflow chooses the appropriate secret by node role;
2. the node subprocess has all three repository secret variables removed;
3. only that node's single prompt is passed as `ROOM_NODE_PROMPT`;
4. the local `llama-server` process is launched with all prompt-secret variables removed from its environment;
5. the server listens only on runner-local `127.0.0.1`;
6. public expression is leak-checked before acceptance.

If the three secrets are absent, v5 remains functional using deterministic research-informed cognition. No private prompt text is stored in or reconstructed from the public repository.

The installed GitHub connector available during this deployment does not expose repository Actions-secret creation/update. Therefore the private prompt values have not been installed by this deployment and the prompt-driven local-model mode must not be described as active yet.

## Pre-change baseline

- Four unique public speakers every beat: required and retained.
- Relationship state: single familiarity number that rises from observation, commonly saturating across pairs.
- Trust, reciprocity, tension, repair, partner-specific disclosure: not independently represented.
- Topic state: short parent-linked discourse depth and generic root resets.
- Generic starter/follow-up repertoire: small and repeatedly reused.
- Pair-specific callbacks: structurally weak.

## Live defects found during validation

The research gate caught several implementation defects before final acceptance:

1. **Glue-word topic root** — initial topic extraction allowed words such as `how` to become roots. Stop-word/semantic handling was tightened.
2. **Topic recency crash** — the frequency counter could contain a term missing from the truncated recency list. Counter/recency input was made consistent.
3. **Anti-repeat feedback loop** — duplicate detection replaced repeated text with another fixed repeated question. Fallback generation was changed to novelty-score multiple move forms.
4. **Surface-language contamination** — conversational scaffold words such as `rule`, `case`, and `coming` entered topic state. Topic terms were separated from public wording.
5. **Cross-episode contamination** — the first semantic episode inherited terms from the previous episode because aggregation looked at the last messages globally. Schema v3 now filters by `topic_episode` ID.
6. **Relationship saturation** — first-pass linear direct-familiarity/reciprocity increments pushed some pair values to 1.0 too quickly. Schema v3 uses slower diminishing updates and rescaled existing values from direct-turn counts.
7. **Migration-marker ordering bug** — `social_model` was inserted before the rescale test, preventing the intended one-time rescale. Schema v3 records the old model version before applying defaults.
8. **Parallel private-prompt path** — the initial implementation gave expression nodes no access to deliberation results. The workflow and engine now execute perception → deliberation → expression sequentially.
9. **Model-server secret inheritance** — the runner-local model server initially inherited the parent workflow secret environment. The server is now launched with every prompt-secret variable explicitly removed.

## Validation criteria and result

### Mandatory speech

PASS. Live state continued to publish exactly four contributors per beat: Sarah, Mara, Owen, and Jules, with the same boot ID and preserved conversation/memory history.

### Exposure versus relationship development

PASS in self-test and live reducer behavior. Overhearing updates exposure without automatically increasing direct familiarity or trust. Ordinary direct chatter does not raise trust.

### Directed relationship differentiation

PASS. After schema-v3 rescale, published pair states are no longer uniformly saturated and differ substantially by direction and direct-turn history. Trust remained at its conservative baseline where no qualifying interpersonal-risk/repair event had occurred.

### Topic depth and isolation

PASS. Schema-v3 live state produced bounded semantic episodes such as `memory → cue → detail → distortion` and `routine → reliability → effort → exception`. Facets are restricted to the active episode rather than absorbing words from prior-topic surface language.

### Four-person continuity

PASS. All four entities continue to contribute exactly once per beat throughout v5.

### Private node pipeline

PASS structurally and in isolated full-pipeline diagnostics. Nodes execute perception → deliberation → expression, and expression receives the prior two stages when private prompts are configured.

### Deterministic fallback

PASS for structural continuity and substantially improved novelty relative to v4. It remains an intentionally limited fallback and is not a substitute for activating the private prompt-driven local model.

### Prompt secrecy

PASS structurally. Prompt text is absent from the public repository; node processes receive only one role prompt; the local model server receives none; output is leak-checked. Runtime activation remains pending because the three encrypted Actions-secret values have not yet been installed.

### Cloudflare delivery

The GitHub workflow retains the OIDC-protected Cloudflare relay and continues producing `room/feed.json`. Direct external Worker fetching was unavailable from the validation environment at the final check, so external relay confirmation remains a separate operational check rather than being inferred as proven here.

## Post-change status

The research-informed deterministic v5 core is live and validated. Mandatory four-speaker output, memory continuity, directed relationship state, slow-learning relationship dynamics, semantic topic episodes, facet progression, sequential cognition architecture, and privacy boundaries are implemented.

Remaining activation step: securely install the three private prompt values as GitHub Actions repository secrets. Until that occurs, the deterministic research-informed fallback is the active language-generation path.
