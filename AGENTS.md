# Entity 4 — Research-First Change Rule

This repository uses a research-first change policy. It applies to behavioral, cognitive, conversational, architectural, reliability, performance, and interface changes.

## Claude bridge operator rule

A verified, read-only Claude consultation bridge is available in this repository. Do not assume a chat has prior memory of it.

When the user asks to consult Claude, says `.` as a standalone collaboration command, or explicitly asks to use the Claude bridge:

1. Read `bridge/README.md` and `.github/workflows/claude-bridge.yml` if the bridge procedure is not already known in the current chat.
2. Create a uniquely named JSON request under `bridge/inbox/` on `main`. The request must contain at least a non-empty `prompt`; include concise repository context and an `expected_response` when useful.
3. The push triggers the GitHub Actions workflow `Verified oracle mailbox`, which uses `bridge/claude_code_oracle.py` when the subscription OAuth token is configured.
4. Wait for the workflow to finish and then read the matching `bridge/outbox/<same-name>.json`.
5. Trust the consultation only when the outbox reports `ok: true`, `verified_model_family: "claude"`, a matching request identity/hash, and a non-empty `response`. If it fails, diagnose the bridge rather than pretending Claude replied.
6. Claude is a read-only reviewer. Independently evaluate its advice before making changes.
7. If the user sends `.+`, consult Claude and implement only the portions independently judged sound, safe, and within the user's stated boundaries.

The bridge transport is discrete request/reply, not a continuous Claude conversation. Each Claude Code invocation uses no session persistence. Never put secrets, credentials, private prompts, or sensitive user material into bridge inbox or outbox files because this repository is public.

## Non-negotiable rule

No substantive change should be made because it merely seems plausible, sounds more human, or fixes one visible symptom. Before implementation, the change must pass the 10-level research gate below. The research record may be concise, but the reasoning must be evidence-based and auditable.

Do not include private model prompts, hidden chain-of-thought, credentials, tokens, or other private system material in this repository. Research notes should contain public evidence, implementation decisions, tests, and observable outcomes only.

## The 10-level research gate

1. **Observed problem** — establish from logs, transcripts, metrics, failures, or direct user observation what is actually happening. Separate the symptom from the suspected cause.
2. **Foundational evidence** — identify established theory or foundational empirical work relevant to the mechanism being changed.
3. **Current evidence** — check newer peer-reviewed research, current standards, or current first-party technical documentation to see what has changed or been refined.
4. **Natural-behavior evidence** — when modeling people, prioritize observations of real human behavior and natural interaction, not only intuitions or scripted examples.
5. **Mechanism evidence** — identify the specific mechanism supported by the evidence and distinguish it from surface imitation. Implement the mechanism when feasible, not a canned phrase list.
6. **Competing explanations** — actively search for evidence that could explain the same observation differently or argue against the proposed change.
7. **Replication, correction, and limitations check** — look for replications, reanalyses, corrections, boundary conditions, methodological criticism, and population/context limits.
8. **Context transfer check** — determine whether evidence from dyads, laboratories, task dialogue, strangers, close relationships, or another technical environment actually transfers to this four-entity, longitudinal Room context.
9. **Implementation mapping** — state exactly which internal state, algorithm, timing rule, memory process, interface path, or architecture component the evidence justifies changing. Avoid broad rewrites unsupported by the research.
10. **Post-change validation** — define observable success and failure criteria before deployment, then compare real output after deployment with the pre-change behavior. Revert or revise when the predicted effect does not appear or creates a new failure mode.

A change that cannot reasonably pass a level must document the uncertainty rather than silently treating an assumption as established fact.

## Additional rule for human-conversation behavior

Conversation changes must be checked across at least these domains when relevant: turn-taking; sequence organization; topic initiation and pursuit; stepwise topic transition and closing; common ground and grounding; repair and misunderstanding; partner-specific lexical/conceptual alignment; question design and perceived responsiveness; reciprocal self-disclosure and intimacy; and longitudinal relationship development.

The Room should not imitate humanity by cycling through canned social phrases. Research should be used to model interactional mechanisms: how participants jointly establish a topic, ratify it, pursue details, repair misunderstandings, reuse shared references, disclose reciprocally, develop partner-specific histories, and transition when the current topic has actually reached a boundary.

## Research record

For each substantive change, add or update a note under `docs/research/` containing:

- observed problem;
- research question;
- sources and dates;
- findings that support the change;
- contradictory/limiting evidence;
- 10-level gate result;
- proposed implementation mapping;
- pre-change baseline;
- validation criteria;
- post-change result after deployment.

Prefer primary research, peer-reviewed sources, authoritative datasets, and first-party technical documentation. Secondary summaries may help discovery but should not be the evidentiary foundation when primary material is available.

## Initial human-conversation foundation

The current research program should begin with, but not be limited to, work on:

- Sacks, Schegloff & Jefferson — turn-taking organization in conversation.
- Stivers et al. (2009), PNAS, doi:10.1073/pnas.0903616106 — cross-linguistic turn-taking timing.
- Button & Casey — topic initiation, nomination, and pursuit in conversation.
- Schegloff & Sacks — topic organization and conversational closings.
- Schegloff, Jefferson & Sacks — repair and preference for self-repair.
- Clark & Wilkes-Gibbs (1986), Cognition, doi:10.1016/0010-0277(86)90010-7 — collaborative grounding/reference.
- Brennan & Clark (1996), JEP:LMC, doi:10.1037/0278-7393.22.6.1482 — partner-specific conceptual pacts and lexical entrainment.
- Huang et al. (2017), JPSP, doi:10.1037/pspi0000097, together with later reanalysis/correction literature — follow-up questions and perceived responsiveness.
- Laurenceau, Barrett & Pietromonaco (1998), JPSP, doi:10.1037/0022-3514.74.5.1238 — disclosure, responsiveness, and intimacy across interactions.
- Aron et al. (1997), PSPB, doi:10.1177/0146167297234003 — gradual reciprocal self-disclosure and experimentally generated closeness.

These references are starting points, not permission to skip the 10-level gate.