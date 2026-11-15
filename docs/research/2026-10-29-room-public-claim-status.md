# Room: Public claims are not witnessed facts (2026-10-29)

## Observed issue and evidence
At live cycle 36294, Owen asked Mara whether she had noticed something *when she moved a microphone cable*, without any recorded public action by Mara. The preexisting shared-scene ledger admits turns with >=2 terms overlapping their speaker's private card, regardless of whether the turn is a question. In a choir scene, Owen's question can therefore become "WITNESSED SHARED EVIDENCE" simply because it mentions "microphone cable". This is false common-ground laundering. A question is only evidence of asking, not of its presupposition.

A verified, read-only Claude consultation at `bridge/outbox/room-epistemic-uptake-review-20261029-1700.json` independently identified this risk, but its claims about match counts require actual fixture tests; we do not treat the consultation as proof. The public text is still a genuine authored turn, not an authenticated record of physical events.

## Foundational and newer evidence
Clark & Wilkes-Gibbs (1986), DOI 10.1016/0010-0277(86)90010-7, and Brennan & Clark (1996), DOI 10.1037/0278-7393.22.6.1482, distinguish participant contributions from shared, negotiated reference. Recent CollabSim work (Microsoft Research, June 2026) emphasizes common-ground quality and repair, not merely fluent output. A source excerpt must remain attributed as a spoken claim, and only an explicit witnessed action can advance a fictional environment.

## Implementation
Continue to include at most one source-bearing public statement per character when it overlaps the speaker's private clue, but do not elevate a question as an asserted observation. Admit a firsthand report of an observation with a more permissive one-distinctive-term threshold, while requiring two terms for other declarative claims. Preserve verbatim public wording; never promote a private card to public knowledge. Label the group ledger as "CLAIMS SPOKEN ALOUD; NOT INDEPENDENTLY VERIFIED", leaving witnessed physical effects in their separate action ledger. Prefer a firsthand report over a less-grounded earlier statement by the same speaker.

## Alternatives and caveats
This is a conservative syntactic proxy for speech-act status. Some questions contain genuine observations, and some declarative reports are mistaken. False negatives may reduce memory recall. Overly permissive firsthand detection may incorrectly promote speculative accounts. More powerful semantic entailment would add inference cost and risk new model failures. The change does not force a speaker to answer and does not solve the larger problem of superficial question chains.

## Research/validation gates
1 Public error observed; 2-4 conversation grounding and repair evidence; 5 status-sensitive shared-memory mechanism; 6-7 alternative parser failures and model-generated errors acknowledged; 8 text-only four-agent transfer cannot be assumed; 9 minimal isolated ledger change; 10 regression tests for real-world question presupposition, firsthand observation, visitor precedence, scene boundaries, actor scope, no private-card leakage, and full Room CI.

After deployment verify that unsupported questions no longer appear in source-labelled knowledge, real observations remain available, and the room does not become less responsive. CI success is not by itself conversational-quality success.
