# Room recipient evidence and action-sequence repair (2026-10-28)

## Observed problem
The public Room transcript at 2026-10-28T12:00:04.873772Z contains Jules saying "Hey Sarah, can you tell me about the new exercise idea you want to explore?" (source ID `20261028T120004873-jules-v5`), while the published `cognition.target` was `mara`. An audit of 100 recent turns found one such explicit recipient mismatch and three adjacent verbatim repetitions. These are observed facts, not a measured estimate for other time windows.

## Research question
When a private model partner and the spoken turn's audible recipient disagree, what is the correct source of conversational responsibility and stored addressee?

## Evidence and 10-level gate
1. **Observation**: A witnessed vocative contradicts private target metadata in the real transcript.
2. **Foundational**: Sacks, Schegloff and Jefferson (1974), *Language* 50(4), 696-735, DOI 10.2307/412243: turn-taking is locally managed and sensitive to recipient design.
3. **Current**: Reprint and commentary in *Language* (2025), DOI 10.1353/lan.2025.a954231; the original turn-taking model remains a useful starting point, not a complete computational algorithm.
4. **Natural behavior**: An explicitly addressed recipient can be invited to produce a next turn; a bystander hearing the question is not automatically its addressee.
5. **Mechanism**: Use observable spoken vocatives and source IDs for allocation of an addressed response, instead of hidden model `target` fields.
6. **Competing hypotheses**: The underlying language model could be generating the wrong words; the floor may still choose a poor response even with correct addressee. This change addresses only routing/provenance.
7. **Limits**: Regex vocatives do not cover all conversational addressees (implicit eye gaze, pronouns, indirect address, group invitations). Multiple named recipients are not yet reliably recognized.
8. **Context transfer**: Most conversation-analysis recordings are human dyads or groups. Room is a four-agent text-only simulation; validation must be empirical and ongoing.
9. **Implementation**: `room_conversational_floor.is_directed` ignores contradictory hidden targets when an audible vocative exists; `room_conversation_project.response_project` reserves named response opportunities; `room_private_model_autonomy_legacy._autonomy_compact` prioritizes addressed source as partner; `room_private_commit` records the unique spoken addressee when present.
10. **Post-change validation**: GitHub CI on the final PR head, sandbox publication test, and analysis of multiple live windows for wrong-recipient replies, quote-echoes and sustained meaningful conversation. These tests do not establish semantic quality by themselves.

## Additional grounding evidence
Clark & Wilkes-Gibbs (1986), *Cognition* 22, 1-39, DOI 10.1016/0010-0277(86)90010-7, treats referring as a collaborative, revisable process rather than a one-shot emission. Schegloff, Jefferson & Sacks (1977), *Language* 53(2), 361-382, DOI 10.2307/413107, documents repair as an interactional process. These support later work on action continuity and repairs, not the present narrow regex patch.

## Baseline and non-goals
Baseline: 100 recent turns, one visible explicit-name/hidden-target mismatch and multiple question echoes. Uncertainty: topic coherence and semantic responsiveness remain poor. Non-goals: forbidding repeated words, imposing topic quotas, forcing agreement, fabricating autobiographical memories, or treating publication metadata as proof of understanding.

## Falsification and rollback
- With a public "Hey Sarah" and hidden target "mara", selection, response project and final published target must agree on Sarah.
- A statement merely mentioning Sarah must *not* create a directed opportunity.
- A question addressed to Sarah must not assign Mara/Owen/Jules a direct-response debt.
- Undirected Allen questions must remain available to all eligible participants.
- The old four-voice mode and sleeping-agent behavior must remain valid.
- If any CI test fails, do not merge; inspect and correct the specific failure.
- If deployed behavior regresses, revert the commit or disable the selected floor using the established Room rollback switch.

## Status
Initial implementation in PR #333. Post-change production outcome **not yet established** as of drafting. CI status must be checked against the final HEAD; do not assert success based on older runs.
