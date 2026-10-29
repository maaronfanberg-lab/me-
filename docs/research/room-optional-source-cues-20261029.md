# Optional public cues: source-aware open floor without parroting

**Status:** independent shadow experiment. Off by default. Absolutely no automatic change to the live Room from this PR.

## Observed and alternative diagnoses

The current single-pass expression_project removes the entire last event and public context for nonquestions and unaddressed statements, even though choose_next may have selected the next speaker because the just-finished statement offers conversational uptake. The model therefore cannot build on a specific newly spoken statement unless it is a question, named address, or invitation. Earlier trial PR #336 restored the entire preceding statement; the small 1B model copied full long utterances (3 of 4 initial cases), so exact source restoration failed. A separate full-turn echo gate helps action integrity but not semantic progress. Repeated category-classification topics also linger in persistent state; reducing context can avoid old loops but sacrifices natural feedback.

## Research

- Sacks, Schegloff & Jefferson (1974) on locally organized turn-taking. A turn is often relevant without demanding a particular response.
- Clark & Brennan (1991), Grounding in Communication, https://web.stanford.edu/~clark/1990s/Clark%2C%20H.H.%20_%20Brennan%2C%20S.E.%20_Grounding%20in%20communication_%201991.pdf : common ground is incrementally joint, but simply sharing lexical items does not certify understanding.
- Brennan & Clark (1996), Conceptual Pacts and Lexical Choice in Conversation, DOI 10.1037/0278-7393.22.6.1482: local referents can support continuity without forcing persistent lexical identity.
- Chang & Chen (2026), LOCOMO-CONV, https://aclanthology.org/2026.findings-emnlp.1289/ : memory relevance alone does not guarantee generated response quality.

## Ten-gate reasoning

1. Observe: last statement discarded in unclaimed expression path.
2. Ground: turn-taking is conditional and local rather than demand-every-line.
3. Current evidence: previous 1B model with verbatim statement copies instead of understanding.
4. Natural target: notice optional content, remain free to disagree, repair, continue or shift.
5. Mechanism: supply 2-6 generic-filtered public content cues with source ID and speaker, never full wording.
6. Alternative causes: weak model, stale memories, generic cues, tiny datasets, source content nonsense.
7. Limits: noun cues may not carry proposition or stance; 11-word minimum may miss meaningful short statements.
8. Transfer: information compression is a software approximation, not an empirical model of human cognition.
9. Implementation: opt-in ROOM_OPTIONAL_SOURCE_CUES experiment, active only on nonquestions with 11+ words, no synthetic dialogue, no memory edits.
10. Validate: pass existing project tests and new opt-in gating tests; compare same-seed 1B full speech in six pairs and six-turn continuations, with human qualitative review. Reject if generic, repetitious, disconnected or fabricated.

## Important protections

Allen's and directed-question handling remain unchanged. Short remarks, scaffolds and prior category-classification fragments do not become anchors. No global topic persistence, speaker quotas, ban lists, canned lines or semantic-overlap false-certification. The opt-in flag is disabled by default and no model-generated text enters public persistent state.

## Outcome

Pending actual isolated model utterances and live causal assessment.
