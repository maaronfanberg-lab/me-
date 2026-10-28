# Research-first Room conversational-floor audit, 2026-10-28

Status: **branch-only research / not deployed**. These are **100 falsifiable engineering checks**, NOT 100 proven defects and NOT 100 completed fixes. Each must be exercised and scored separately. No restrictions on vocabulary or synthetic topic rotation.

## Observed problem and pre-change baseline

- From `room/feed.json` near cycle 34681 (2026-10-28T23:26:14Z): 160 autonomous public turns, 6 exact adjacent whole-turn duplicates and 15 utterances of 1–3 words. These are *diagnostics*, not an algorithm for deciding naturalness.
- Examples: Jules says `Hey, what's next?`, Mara asks `Hey, what's the next point to tackle in this conversation?`; Jules asks whether others have tried exploratory experimentation; Owen echoes that question; Mara echoes Jules's full invitation. There are also standalone `try` and `disclosure` turns.
- `room/state.json`: `conversational_floor: opportunity_v1`, `active: true`, `diagnostic_only: true`; prior state includes a topic episode of over 2,300 turns and a pending bridge. The status flag is hard-coded in `scripts/room_private_commit.py`, so it is not a trustworthy test of complete behavioral enforcement.
- Confirmed code mismatch: `choose_next` can choose an open-floor uptake from a prior non-question; `expression_project` classifies that same prior non-question as independent initiative and strips both `event` and `context`. `_autonomy_compact` then explicitly forces `event=None`. The model may therefore receive a prompt that lacks the preceding utterance it could have picked up. This is an explanatory *hypothesis* for incoherence, not a proven sole cause.
- Other plausible contributors include weak 1B generator quality, context packing, fallback/model retries, expired group activities, and absence of semantic adequacy judging. No one root cause has been established as sufficient.

## Research question

Does retaining a *single provenance-tagged, optional previous public turn* on unaddressed nonquestion opportunities improve connectedness while preserving genuine initiative and reducing stale-topic contamination?

## Evidence, applicability, and limitations

Conversation-analysis research documents turn-taking, conditional relevance of responses to questions, sequence expansion and repair; it **does not imply** all statements demand responses. Collaborative grounding is an iterative mutual achievement, not simply lexical overlap. Human multiparty timing findings are evidence for responsiveness, not justification for timed speaker quotas. AutoGen selector group chat demonstrates contextual speaker selection but does not solve semantic uptake. Modern multi-turn model research warns that error accumulation is substantial.

1. https://academic.oup.com/edited-volume/61882/chapter/547683169
2. https://academic.oup.com/edited-volume/61798/chapter-abstract/546199718
3. https://www.sciencedirect.com/science/article/pii/0010027786900107
4. https://pubmed.ncbi.nlm.nih.gov/19553212/
5. https://www.conversationanalysis.org/schegloff-media-archive/preference-for-self-correction-in-repair-in-conversation-1977/
6. https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/selector-group-chat.html
7. https://www.microsoft.com/en-us/research/publication/llms-get-lost-in-multi-turn-conversation/
8. https://aclanthology.org/2025.findings-acl.958/

## 10-level gate

1. Observed issue: empirical sample plus exact confirmed source-drop code path.
2. Foundation: Sacks/Schegloff/Jefferson; Sidnell (Oxford); Clark/Wilkes-Gibbs.
3. Current research: Oxford sequence overview; modern multi-turn and AutoGen technical documentation.
4. Natural behavior: adjacency pair, third-position repair, optional uptake; never impose a speaker schedule.
5. Mechanism: preserve conditional relevance and accessible prior evidence without imposing it as a command.
6. Alternative explanations: weak local model, diffusion from old memory, truncation, retry/fallback interactions, topic attractor.
7. Limits/replication: cited findings are mostly human dyads/task dialogue; cannot guarantee these 4 synthetic agents behave well.
8. Context transfer: open-floor group conversational selection differs from classic dyads; require observed longitudinal evaluation.
9. Implementation mapping: optional source projection in `room_conversation_project.py`, source identity in `room_private_model_autonomy_legacy.py`, explicit tests for contextual continuity and autonomy.
10. Validation: baseline freeze, deterministic tests, model-run comparative trial, live 30–50 consecutive turns post-deploy with manual judgments; roll back if quality worsens.


## Implementation / review audit at branch revision

- Verified Claude consultation: `bridge/outbox/claude-consult-20261028-context-loss-34681-02.json` has `ok: true` and `verified_model_family: claude`; identity `claude-consult-20261028-context-loss-34681-02`. The first full repository-review request exceeded Claude's four-turn limit and supplied **no** verified guidance. The successful independent Claude reviewer was **context-only**, not a direct source audit. It supported the narrow optional-anchor hypothesis and explicitly advised against treating it as the only cause.
- Source-level fix on this branch only: retain the *latest exact witnessed autonomous public statement* for optional uptake **only** when the current floor selection has matching reason (`open_floor_uptake` or `open_floor_relevance`), speaker, and source ID, and the source is neither self-speech nor directed to another character. Do not inject old topic terms, group memories, canned lines or word bans.
- Follow-up source audit revealed that **successfully deliberated** opportunities typically use `open_floor_relevance`, while `open_floor_uptake` is the no-deliberation fallback. The first patch erroneously covered only the latter. Branch tests and fix now cover both reasons, while maintaining source/speaker matching and optionality. Actual production proportion of those reasons has not been measured.
- Runner binds `ROOM_FLOOR_REASON`, `ROOM_FLOOR_SOURCE_ID`, `ROOM_FLOOR_SPEAKER` exclusively to the selected expression process. The model payload still allows independent initiative. Existing question/invitation replies and directed addressee protections are preserved.
- Added exact boundary tests for public anchor retention, speaker/source mismatches, and directed/self/system speech; read-only evidence reporter and observational tests. All tests are source-level/sandbox tests; no 1B-model live or shadow conversational quality benchmark has been completed.
- Dedicated conversational-floor CI is **green** through integrated selector/source tests: GitHub Actions run `40788283691` for revision `e24a43fa1aef4f9aa4dc6b60a4891d52dc80adbf`. Room Attention Smoke is green (`40788283802`). Earlier evidence-reporter fixture failed because the preceding question also had 3 words; the fixture was corrected and rerun successfully. The same later architecture test remains red (`40788283706`) due to a viewer-history assertion, outside the changed code.
- Independent architecture smoke workflow `40787772794` failed a **pre-existing, unrelated viewer-history assertion**: `viewer does not load the pre-reset semantic archive`. It is not proof this conversational patch failed nor a pass for the overall repository. Remains an open separate item.
- Live system has **not** been changed; production has **not** been updated; there is **no verified improvement in sustained conversation**. Draft PR `#336` remains unmerged.
- The 100 items below are audit probes, not completed blockers. Relevant source checks verified by code and tests include source identity, audible addressed turns, no unauthorized private anchors, and branch-only tests; remaining semantic outcomes require model and human assessment.

## One hundred blocker probes (all start as unverified until exercised)

### Evidence and baseline

- [ ] B001 · Record sample SHA/cycle/time
- [ ] B002 · Exclude system records from turn counts
- [ ] B003 · Count exact consecutive duplicates
- [ ] B004 · Count short-turn rate without treating it as failure
- [ ] B005 · Count question/answer sequences
- [ ] B006 · Count repeated unanswered question sequences
- [ ] B007 · Count source-linked contributions
- [ ] B008 · Count participants in each 20-turn window
- [ ] B009 · Track recurring meta-conversation phrases
- [ ] B010 · Keep immutable before/after transcript windows

### Floor selection

- [ ] B011 · Select audible named addressee
- [ ] B012 · Do not trust hidden targets over vocatives
- [ ] B013 · Preserve ambiguity with multiple addressees
- [ ] B014 · Honor accepted human turns
- [ ] B015 · Never select sleeping agents
- [ ] B016 · Do not assume a question implies agreement
- [ ] B017 · Preserve legitimate same-speaker continuation
- [ ] B018 · Avoid deterministic speaker rotation
- [ ] B019 · Explain candidate selection provenance
- [ ] B020 · Retry only independently eligible candidates

### Source continuity

- [ ] B021 · Keep source id through sensing
- [ ] B022 · Keep source id through deliberation
- [ ] B023 · Keep source id through expression
- [ ] B024 · Keep source id in preflight
- [ ] B025 · Keep source id in commit
- [ ] B026 · Retain latest non-question as optional context
- [ ] B027 · Retain literal asked question
- [ ] B028 · Retain direct invitation content
- [ ] B029 · Avoid stale quoted history as initiative prompt
- [ ] B030 · Verify latest turn is not replaced by previous candidate

### Sequence organization

- [ ] B031 · Recognize questions as pending action
- [ ] B032 · Recognize invitations as pending action
- [ ] B033 · Recognize proposals without presuming acceptance
- [ ] B034 · Permit explicit refusal
- [ ] B035 · Permit qualified disagreement
- [ ] B036 · Permit relevant counterquestion
- [ ] B037 · Permit short legitimate acknowledgment
- [ ] B038 · Permit third-position receipt
- [ ] B039 · Avoid discarding an unanswered source after one turn
- [ ] B040 · Track closure of actual action not arbitrary turn quota

### Repair and grounding

- [ ] B041 · Allow one clarification request
- [ ] B042 · Detect identical unrepaired question echo
- [ ] B043 · Preserve first repair opportunity
- [ ] B044 · Permit self-repair
- [ ] B045 · Permit other-initiated repair
- [ ] B046 · Preserve corrected shared reference
- [ ] B047 · Distinguish quote from unacknowledged echo
- [ ] B048 · Do not force endorsement
- [ ] B049 · Do not invent shared knowledge
- [ ] B050 · Test return to main sequence after repair

### Natural topic management

- [ ] B051 · Avoid fixed subject blacklists
- [ ] B052 · Do not synthesize arbitrary new topic vocabulary
- [ ] B053 · Permit coherent topic closure
- [ ] B054 · Permit stepwise segue
- [ ] B055 · Permit principled abrupt change
- [ ] B056 · Avoid hard minimum topic length
- [ ] B057 · Retire topic attractors only with evidence
- [ ] B058 · Avoid global stale topic on optional uptake
- [ ] B059 · Record disagreement tied to actual source
- [ ] B060 · Do not treat topic word overlap as comprehension

### Memory and character

- [ ] B061 · Use provenance-tagged memories
- [ ] B062 · Avoid treating reported speech as fact
- [ ] B063 · Preserve partner-specific knowledge
- [ ] B064 · Avoid hallucinated shared history
- [ ] B065 · Honor stable authored interests
- [ ] B066 · Avoid repeated stale memory retrieval
- [ ] B067 · Carry genuine unresolved commitments
- [ ] B068 · Prevent topic residue in independent initiative
- [ ] B069 · Allow personal perspective differences
- [ ] B070 · Check social sensitivity of corrections

### Generation and quality

- [ ] B071 · Detect clipped invalid structured output
- [ ] B072 · Reject private prompt leakage
- [ ] B073 · Reject internal schema meta-talk
- [ ] B074 · Reject sampler collapse
- [ ] B075 · Retain valid very short answers
- [ ] B076 · Detect structurally empty move labels
- [ ] B077 · Check utterance linked to expected action
- [ ] B078 · Require specific response evidence for answer claims
- [ ] B079 · Bound regeneration to prevent cost spirals
- [ ] B080 · Allow abstention path when all candidates fail

### Operational reliability

- [ ] B081 · Test rank-zero candidate generation
- [ ] B082 · Test rank-one technical fallback
- [ ] B083 · Prevent partial state mutation on rejection
- [ ] B084 · Check commit uses same candidate source
- [ ] B085 · Detect racing concurrent live updates
- [ ] B086 · Avoid silent legacy quality fallback
- [ ] B087 · Check restart from transient model fault
- [ ] B088 · Preserve public queue acknowledgment
- [ ] B089 · Ensure diagnostics are not confused with enforcement
- [ ] B090 · Verify production brain identity per beat

### Validation and rollout

- [ ] B091 · Execute existing Python regression suite
- [ ] B092 · Run 100 scenario checks as designed
- [ ] B093 · Compare untouched baseline against candidate
- [ ] B094 · Test without provider model first
- [ ] B095 · Test with actual room brain when available
- [ ] B096 · Measure consecutive multi-turn responsive spans
- [ ] B097 · Review sampled turns for genuine relevance
- [ ] B098 · Compare topic continuity without quota
- [ ] B099 · Publish branch CI evidence before merge
- [ ] B100 · Require actual live post-deploy verification

## Stage gates

- **Gate A**: research evidence plus independent verified reviewer response, or explicitly recorded reviewer failure.
- **Gate B**: create failing regression for open-floor source loss; add minimal context-retention change; run all relevant existing tests.
- **Gate C**: CI green on branch, review false-positive behavior and model plausibility.
- **Gate D**: compare production-brain generated transcripts with baseline before deploy. No unreviewed automatic main merge.
- **Gate E**: post-deploy verify live active selection and substantive multi-turn response continuity. `diagnostic_only` must not be relabeled as comprehensive semantic enforcement without evidence.

## Production canary acceptance and rollback criteria

The release is *not* successful because code merged or a label changed. The active runner must be restarted on the merged commit, and `room/state.json` must then contain `conversational_floor_health.source_anchor_version=optional_selected_public_v1` with `active=true`. This proves the new runner code loaded, **not** that substantive conversational grounding is effective.

Use exact post-release source IDs and evaluate at least 30 consecutive autonomous public turns, expanding to 80 if possible. A human reviewer must find at least one coherent **five-turn** conversational sequence in which different characters reference and develop the same concrete matter, including a response, a follow-up, and a further contribution. The sequence must not consist of restating an invitation or announcing a new topic. Independently calculate exact repeated-turn runs, short-turn share, participant mix and source relevance, but never use those proxies alone to declare success. Retain authentic short replies and valid repair.

Reject/roll back if there are privacy leaks, source-corruption, repeated unanswered echo loops, an increased rate of disconnected meta-conversation, or no observable improvement over contemporaneous pre-deploy samples. Record honest false negatives: zero enforced topic quotas, no scripted lines, and no blanket repeated-word bans. After promotion, update this document with exact cycles, timestamps, run IDs, samples and limitations.

## Post-change result

Not run. Branch not deployed. Claude review pending or retry in progress.
