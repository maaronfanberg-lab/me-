# Open-floor opportunity without fabricated personality bids

**Status:** independent draft PR, not merged or deployed. Do not claim that equal participation means a better conversation.

## Observed problem

Public room/feed.json near 2026-10-28T23:40Z: 160 autonomous turns, approximately Jules 66, Mara 56, Owen 28 and Sarah 10. A single window cannot establish a long-term distribution but warrants investigation. In scripts/room_conversational_floor.py the static curiosity/extraversion/inhibition terms yield approximate baseline scores Sarah .0863, Mara .0964, Owen .0750, Jules .1032 using current published traits. Live room_private_model_autonomy.run('thought') returns None by design. These personality scores therefore rank opportunities **without any current character bid**, while relationships and local contextual evidence may add further factors.

## Question and alternative explanations

When there is no separate model deliberation and no audible addressee, should a fixed extroversion value decide who speaks? Hypothesis: no. A disposition colors speech but is not evidence of a bid for this turn. Alternative causes include source mentions, outstanding questions, asymmetric relationships, per-voice model failures and selective sample windows.

## Evidence and applicability

- Sacks, Schegloff & Jefferson (1974), *A simplest systematics for the organization of turn-taking for conversation*, Language 50(4), 696–735, DOI 10.2307/412243. Turn management is locally organized and recipient-sensitive.
- Clark & Wilkes-Gibbs (1986), *Referring as a collaborative process*, Cognition 22, 1–39, DOI 10.1016/0010-0277(86)90010-7. Grounding is a joint achievement, not inferred from disposition.
- These studies concern human interaction and do NOT imply evenly distributed turns, speaking quotas, or an optimal random algorithm for synthetic characters.

## Ten-level research gate

1. Observed issue: live sample, score code, single-pass lack of independent private thought.
2. Foundation: turn-taking conditional relevance and recipient design.
3. Current literature: review modern multi-turn agent failure evidence; restrict intervention to one fallback.
4. Natural behavior: preserve audible address and responsiveness to prior questions.
5. Mechanism: distinguish actual current bidding from permanent personality disposition.
6. Alternatives: model failure, partners, source mentions, cumulative relationship scores.
7. Limitations: 160 turns do not establish causality; test many independent sources.
8. Transfer: no real-time embodied human bids; deterministic source tie-break is an engineering approximation.
9. Mapping: in the public_uptake fallback, rank by witnessed local relevance and prior questions, not static trait priority. Leave deliberated and addressed paths intact.
10. Validation: 96 neutral source IDs across exaggerated profiles; no static speaker monopoly; existing directed, sleeping, and repair tests unchanged. Compare real consecutive turns after deployment; revert if naturalness worsens.

## Acceptance and non-goals

Initial intentionally failing regression verifies a stable personality winner on neutral public turns. After a narrow fix, a deterministic source-linked tie-break may allow each otherwise eligible speaker some unclaimed-floor opportunities. No quotas, no speaker rotation, no banned vocabulary and no invented private willingness. Distribution improvement is never proof of actual conversational quality.

Deployment: **none**. Independently assess following source-retention PR #336 before combining or promoting.
