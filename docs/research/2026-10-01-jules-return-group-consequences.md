# Jules returns: remembered encounters and opt-in joint work

## Observed problem and research question

Alex requested Jules's return with differentiated evolving relationships,
specific memory, initiatives that require cooperation, and genuine revision
when corrected. The inspected main configuration marked Jules asleep; the
engine and commit boundary excluded Jules and froze private observations.
The live feed at 2026-10-01T01:39:44Z, cycle 8105, used llama3.2-1b and listed
Jules asleep. Its eight latest messages repeatedly discussed belief, apologies,
misunderstanding and insensitivity. That is a local baseline, not evidence that
all earlier conversation had this pattern.

Question: can a small, inspectable state mechanism make an invitation,
contribution or correction consequential across turns without preloading
alliances or inventing history? The active autonomy module is single-pass;
adding extra perception/thought model calls would conflict with that design.

## Sources checked on 2026-10-01

- Clark & Wilkes-Gibbs (1986), *Referring as a collaborative process*:
  https://doi.org/10.1016/0010-0277(86)90010-7
- Brennan & Clark (1996), *Conceptual pacts and lexical choice in conversation*:
  https://pubmed.ncbi.nlm.nih.gov/8921603/
- *The Flexibility of Conceptual Pacts* (2016), primary experiments:
  https://pubmed.ncbi.nlm.nih.gov/27199801/
- Dingemanse et al. (2015), natural conversation across twelve languages:
  https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0136100
- Park et al. (2023), *Generative Agents*, architecture, ablation and errors:
  https://arxiv.org/html/2304.03442v2
- Taillandier et al., arXiv:2507.19364 (2025; current revised title
  *From the Fluency Fallacy to the Micro-to-Macro Validity Gap*):
  https://arxiv.org/abs/2507.19364
  This methodological position paper is a limitation check, not an empirical
  replication establishing this Room's validity.

## Findings and boundaries

Reference can be jointly established and partner-specific, but conceptual pacts
are revisable rather than permanent. Natural repair sequences are often specific
to the trouble being addressed; a generic apology is weak evidence of what was
corrected. Agent research motivates retrieving observed experiences and tracking
plans, while reporting memory retrieval failures and embellishments. Fluency does
not establish realistic social behavior. These findings support explicit history
and revision mechanisms; they do not justify a prescribed friendship, an inferred
inner motive, or empirically calibrated trust increments for these four agents.

## Ten-level gate

| Level | Decision and uncertainty |
| --- | --- |
| 1: Observation | Nap flag, frozen state, active model and timestamped repetitive sample verified in main. |
| 2: Foundation | Collaborative grounding and partner-specific history motivate directional recall. |
| 3: Current evidence | Checked current primary agent paper and revised 2025 methodological paper; retain single-pass architecture. |
| 4: Natural behavior | Twelve-language informal repair corpus supports concrete trouble-source references; no claim of human equivalence. |
| 5: Mechanism | Store observed exchanges, opt-in activity responses, offered work and cited self-corrections; retrieve before expression. |
| 6: Alternatives | Small-model capacity, filtering, masking and active topical repetition could explain flat dialogue; persona wording alone may not help. |
| 7: Limits/correction | Conceptual pacts can change; agent recall can embellish. No direct replication of this Room mechanism found. Retain provenance and copy guards. |
| 8: Transfer | Human dyads and 25-agent simulations differ from this four-agent chat. Transfer is an engineering hypothesis, not an established effect size. |
| 9: Mapping | Narrow optional module, engine payload/partner score, validated commit hook, active Jules variation, nap flag and isolated CI tests. |
| 10: Validation | Define offline causal tests and live presence/input/state checks; distinguish delivery from demonstrated long-term improvement. |

## Implementation mapping

- `room/config.json`: clear the current sleeping list; enable group dynamics.
  Preserve boot ID, existing memories, people and other character profiles.
- `room_group_dynamics.py`: observe only accepted published messages for awake
  listeners. Maintain bounded encounters, activities and acknowledged revisions.
  Retrieve only private encountered speech, with source IDs and epistemic labels.
  No public transcript is retrospectively replayed into Jules's private memory.
- Proposal recognition: a public invitation must name two present peers and a
  concrete subject. Responses require a subject reference or direct adjacency
  to that invitation. A decline is not acceptance; no invitation changes trust.
  Accepted, relevant offered work affects only the organizer's directional
  reciprocity/respect, once per contributor. This marks speech offered as work,
  not verified external completion. Two open activities maximum; eight-cycle
  proposer cooldown; expiry after 48 inactive cycles; twelve retained activities.
- Explicit revisions must refer to an earlier observed peer statement addressed
  to the reviser with overlapping content. The record states acknowledged
  revision, not verified truth; it modestly changes that directional respect.
- Pending accepted work modestly biases partner selection; declined/closed work
  does not. Normal address routing and Allen participation remain intact.
- `room_engine_v5.py`: attach bounded per-agent relationships, remembered speech,
  activities and latest revision to the active expression payload.
- `room_private_commit.py`: update consequences after the public validation and
  recording boundary; rejected candidates never enter the new memory.
- `room_private_model_autonomy.py`: Jules values specific comparisons and
  follow-through, remains fallible, and can invite two collaborators. Existing
  single-pass generation, pronouns, individual differences and public quality
  gates remain. The speech guard also checks retrieved memory for copied spans.
- Tests run inside disposable fixtures because engine imports initialise state.
  The old nap test now explicitly supplies an asleep configuration, so production
  no longer needs to keep Jules asleep merely to satisfy that regression test.

Conservative English recognisers can miss paraphrased invitations, acceptances
and corrections, and topical word overlap can falsely connect responses. Their
coverage is deliberately limited and auditable. They are not sentiment analysis,
theory of mind, consent for anything outside this conversational task, or a claim
of objectively measured relationship strength. Small state deltas and scoring
weights are bounded engineering defaults with no human calibration claim.

## Validation criteria and results

Before deployment, require: awake Jules; preserved nap isolation; explicit
accept/decline distinction; no generic-apology work credit; no duplicate delivery
credit; directional relationship change following work; persistence and actual
single-pass model compaction; memory copy rejection; specific revision evidence;
closing removes follow-up pressure; disabled feature is inert; and full validated
publication writes the activity and awake status.

Offline result: both `test_room_group_dynamics.py` and
`test_room_sleeping_entity.py` passed. Compilation and diff whitespace checks
passed. The publication test uses the real final quality gate and substitutes
in-memory persistence; it does not call a language model or certify live wording.

Live criteria: verify main contains the merged implementation; a fresh feed lists
Jules awake and records a newly generated Jules message; a later cognitive-state
snapshot stores grounded encounters and the new group state. Inspect consecutive
beats for quality failures. Delivery is not sufficient evidence of long-term
improvement: over twenty future published beats, look for distinct Jules turns,
source-consistent callbacks, and an optional invitation with independent responses.
If repeated task forcing, false memories, leaked state labels or homogenisation
appear, disable group dynamics and revise the recognisers/profile changes. Do not
reset Room history as a repair.

Post-deployment result: pending live verification at the time of this commit.

GitHub CI: the new presence/group job passed at run 36802648759.
The architecture job passed the engine and all three Allen simulations, then
failed `room_personality_v2_sim.py` at Sarah's pre-existing profile-shape assertion.
That exact assertion was reproduced in an unchanged baseline checkout. The Allen
social simulator failed its old expectation that `progress` remains a valid topic
root; that failure was likewise reproduced against unchanged baseline code. Its
automation also updated the branch's diagnostic timestamp/tested SHA. An unrelated
Emily/Olivia workflow reported a failure; that workflow is outside this change.
No failing gate or assertion was removed or weakened.
