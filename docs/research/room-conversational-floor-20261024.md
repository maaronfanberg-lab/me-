# Room action-contingent turn-taking: research and deployment gate
Date: 2026-10-24. PR #315. Ten-level research gate and first live implementation slice.

## 1. Baseline
The Room's October 24 public feed had 160 recent turns; 151 contained "category" and 144 contained "trees". That measures lexical concentration only, not absence of genuine social meaning. Existing engine independently generated four autonomous speakers every beat and injected four distinct-contribution jobs; the quality layer rejected lexical overlap. The observation motivating change is limited conversational response, repair, and topic movement.

## 2–4. Foundational, current, and natural-interaction evidence
Sacks, Schegloff, and Jefferson (1974), DOI 10.2307/412243: recipient-designated and self-selected next turns as locally organized social interaction. Schegloff et al. (1977), DOI 10.2307/413107: repair can productively repeat earlier speech. Brennan and Clark (1996), DOI 10.1037/0278-7393.22.6.1482: partner-specific conceptual pacts encourage shared reference forms. Nonomura and Mori (2025), DOI 10.3389/frai.2025.1582287: in a four-agent murder-mystery task, combining speaker-selected next with self-selection reduced breakdowns compared with equal turns. Oxford ORCA clinical work on refusals and minimal acknowledgments informs response organization, but does not itself establish universal peer-chat rules.

## 5. Mechanism
A character receives a single conversational opportunity before expression generation. An audible name/vocative plus metadata is evidence for recipient priority; hidden metadata alone is not. In the open floor, previously deliberated goals, partner preference, personality, relationship state, and ongoing unfinished thread influence who speaks. A second candidate is permitted only if the first model fails, not to suppress repeated wording. Speaker realization remains generated, not scripted. Purposeful repeated references and brief acknowledgments are allowed.

## 6. Competing explanations
A 1B/0.5B language-model limitation, model-wrapped prompts, flooded topic scaffolds, repetitious static goals, failure to repair, broken memory/consensus, and four mandatory expressions may all independently cause stagnation. Speaker selection is a bounded first intervention and might not improve dialogue quality.

## 7–8. Replication and limitations
The four-agent empirical setting was structured and time-limited, not a longitudinal unscripted Room. Text does not supply prosody, gaze or pause. Named vocative detection misses indirect social address and ambiguous pronouns. Always selecting a speaker is not truly voluntary silence. A rule against repetition is expressly not the objective; copying can serve clarification, reference and emphasis. The small-model capacity remains a live deployment risk.

## 9. Specific implementation
- scripts/room_conversational_floor.py ranks one addressed or open-floor speaker from observed source and private action, provides bounded technical fallback, and saves observed source ID, cycle key, and deliberation-bus checksum.
- .github/workflows/sarah-society.yml retains eight cognition/thought nodes, generates one selected expression, runs preflight, tries a second candidate only after technical failure, and retains exact original four-expression path when ROOM_CONVERSATIONAL_FLOOR=0. It falls back locally after two failed selected beats and rejects stale Git conversation rebase.
- scripts/room_engine_v5_core.py and scripts/room_private_commit.py validate a nine-part selected beat versus legacy twelve-part beat, verify identities and source evidence, and preserve Allen as a recipient. They quarantine invalid selected expression rather than publishing filler.
- scripts/room_private_model.py and scripts/room_private_model_autonomy_legacy.py along with scripts/room_expression_quality_legacy.py and scripts/room_engine_v5.py stop requiring novel wording, preserve intentional echo/short speech and privacy guards, filter severe within-utterance sampler collapse, and distinguish spoken terms from system topic metadata. They do not yet implement full common-ground state or voluntary silence.
- Unit and sandbox integration tests simulate direct speech, hidden metadata, role and sleep scope, real nine-node commit, Allen recipient, old twelve-node rejection, discarded stale source, repair repetition, sampler collapse and workflow shell syntax.

## 10. Validation and rollback
New floor tests, Room presence/group and attention smoke must pass before merge. The older architecture smoke has a profile-shape mismatch already detectable on main: room/config.json has 23 psychology_v2 keys per character, while scripts/room_personality_v2_sim.py demands 19 keys. Do not delete personality data to make that stale assertion pass. Other unrelated workflow failures are not evidence these tests passed.

Post-merge: inspect the very next Git-authoritative public beats, requiring one autonomous contributor per beat, non-sleeping speaker, accurate addressees, advancing state, preserved Allen events, no repeated model-failure spiral, and feature marker conversational_floor=opportunity_v1. Human-coded interaction-level outcomes (answers, repair, refusal recognition, relationship continuity) must improve or warrant rollback. Lexical variety alone is not an acceptance criterion.

Rollback: ROOM_CONVERSATIONAL_FLOOR=0 restores original expression loop on new jobs; long-running runner automatically falls back after two failed selected beats. Code revert also possible without resetting conversation or memory. Stop immediately on lost Allen input, state corruption, privacy exposure, or persistent failures. Do not claim genuine voluntary silence until the separate durable beat/health protocol (draft PR #314) is fully tested and integrated. Production deployment status and outcome must be reported after actual observation.
