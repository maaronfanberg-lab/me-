# Implementation review: human conversational organization for The Room
**Date:** 2026-10-24. **Stage:** research and adaptation design only; no new production behavior in this document.

## Objective
The goal is not to reduce repeated strings. A character should repeat something whenever it serves grounding, conceptual alignment, storytelling, repair, emotional emphasis, humor, or an unresolved disagreement. A conversation should avoid *empty cycling* by actually accomplishing the next interactional action. A script requiring a "unique contribution" is not equivalent to natural conversational competence.

## Most directly transferable experimental implementation
**Nonomura & Mori (2025), "Who Speaks Next? Multi-party AI Discussion Leveraging the Systematics of Turn-taking in Murder Mystery Games"**, Frontiers in Artificial Intelligence, DOI 10.3389/frai.2025.1582287.
- **Four agents**, with personal role/goal information, short-term thoughts, important memories, shared recent dialogue.
- `think()`: each proposes `speak` or `listen`, a possible intended action, and an importance 0–9.
- `detectDesignation()`: classify the *first pair part* (question/address/invitation, etc.) and intended recipient from the previous public utterance.
- **Current Speaker Selects Next** takes priority when an addressed action projects a response. Otherwise, **self-selection** chooses among willing speakers by importance. When all choose to listen, their demonstration lets the previous speaker continue.
- `speak()` supplies the pertinent second-pair action and personal information, then updates memory.
- **Actual comparison:** equal turn-taking vs self-selection only vs combined current-speaker-selects-next/self-selection. Study used 50 sets of 10-turn conversations per condition, GPT-4o for designation/speech, GPT-3.5 Turbo for thinking/normalization. It reported fewer dialogue breakdowns and ignored questions in the combined condition. **Do not extrapolate** to months-long unscripted text rooms or assume a 1B model will handle the same recognition task.
- Source is a detailed published algorithm/pseudocode; no separately verified public source repository identified here.

## Other source implementations examined

| System / source | Concrete transferable code pattern | Limitations |
|---|---|---|
| **AutoGen SelectorGroupChat** (Microsoft, `_selector_group_chat.py`) | Explicit speaker selection separated from speaker generation; `selector_func` or `candidate_func`; one speaker receives the next action, others listen. Can choose repeated same-speaker turns. | Default selector requires an LLM and may select from role descriptions; does not natively understand conversational obligations or epistemic grounding. Default disallows consecutive speakers, an arbitrary rule not suitable for natural speech. |
| **TRINDI / GoDiS** (Larsson & Traum, 2000) | Dialogue **information state** updated by observed dialogue acts, separating shared commitments and QUD (Questions Under Discussion) from each character's private agenda and beliefs. | Task/dialogue-manager origins, often slot-filling; do not impose a single common ground on contested social interpretation. |
| **OpenDial** (`src/opendial/DialogueState.java`, `DialogueSystem.java`) | Modular state update through a central information hub; probabilistic rules keep uncertainty rather than collapsing every observed message to one truth. | Java/Bayesian network apparatus is heavy for this small Python Room; reuse state-update principle, not framework. |
| **Generative Agents** (Park et al. 2023, original `joonspk-research/generative_agents`, `retrieve.py` and `reflect.py`) | Per-agent observed experience, event- and person-relevant retrieval, higher-level reflections with source pointers, plans altered by new observations. | Reflection based on noisy LM outputs can become self-referential; reflective claims must link to original evidence and cannot count as independent observations. |
| **OpenDialog conversational patterns** (`docs.opendialog.ai`) | Conversation as sequences of action, with independently modelled opening, repair, storytelling, request/refusal, and closing; distinguish retry after *mishearing* from clarification after *misunderstanding*. | Scripted pattern library; Room should infer appropriate next action rather than force canned lines. |
| **IBM user-initiated repair study** (Moore et al. 2024) | Agent utterances themselves may be unclear; allow recipient repair and third-position reworking rather than forcing users/peers to paraphrase their questions. | Demonstrated mainly in human-agent dyadic interfaces; not directly validated for spontaneous four-agent groups. |
| **ConvoKit** (CornellNLP, `coordination/coordination.py`) | Response-linked corpus objects and longitudinal linguistic coordination measures; helpful for **analysis**, not a replacement for conversation control. | Function-word coordination is not the same as conversational progress. Repetition metrics cannot be optimization targets. |
| **SOTOPIA / SOTOPIA-Eval** (ICLR 2024) | Social goal success, relational/strategic interaction and human-rated social competence in held-out scenarios. | Task-specific scored role play differs from open-ended unconstrained group conversation; judges can have bias. |
| **TurnGPT** (Ekstedt et al. open source) | Explicit speaker tags and turn-transition tokens for spoken dialogue. | Speech timing/overlap is not represented in Room's text-only feed; avoid bolting in a spoken-turn predictor as if text provided prosody. |

### Primary implementation/source URLs
- Nonomura & Mori: https://www.frontiersin.org/journals/artificial-intelligence/articles/10.3389/frai.2025.1582287/full
- AutoGen selector docs: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/selector-group-chat.html
- AutoGen source: https://github.com/microsoft/autogen/blob/main/python/packages/autogen-agentchat/src/autogen_agentchat/teams/_group_chat/_selector_group_chat.py
- TRINDI: https://doi.org/10.1017/S1351324900002539
- OpenDial source: https://github.com/plison/opendial/blob/master/src/opendial/DialogueState.java
- Stanford original agents: https://github.com/joonspk-research/generative_agents
- Generative Agents paper: https://doi.org/10.1145/3586183.3606763
- OpenDialog: https://docs.opendialog.ai/opendialog-platform/conversation-designer/conversation-design/conversational-patterns/introduction-to-conversational-patterns
- IBM repair study: https://research.ibm.com/publications/understanding-is-a-two-way-street-user-initiated-repair-on-agent-responses-and-hearing-in-conversational-interfaces
- ConvoKit: https://convokit.cornell.edu/features.html
- SOTOPIA: https://proceedings.iclr.cc/paper_files/paper/2024/hash/b3075b88e583a0e98d8b24338a613060-Abstract-Conference.html
- TurnGPT: https://github.com/ErikEkstedt/TurnGPT
- Grounding survey, categorized 448 papers: https://github.com/tanikina/common-ground-in-dialogue

## Proposed synthesis, adapted to four-person, text-only Room

### 1. Conversation journal: observable *action*, not repeated topical vocabulary
Each emitted utterance appends an immutable event:
```json
{
  "id": "public-message-id",
  "speaker": "mara",
  "recipient_candidates": ["sarah"],
  "action_candidates": [{"kind":"question","confidence":0.88}],
  "refers_to": ["earlier-message-id"],
  "source_span": "Sarah, what makes that example evidence?",
  "epistemic_status": "observed_speech_not_verified_truth"
}
```
Store candidate interpretations **separately from observed words**. Provenance points to the actual utterance and observed recipient. A question may be rhetorical, indirect, hostile or jointly addressed: maintain alternatives rather than assuming every '?' creates one definitive question. Do not assume every `move_type` supplied by the generator is true.

### 2. Per-participant interaction state (TRINDI pattern + local observation)
Keep separate for each participant:
- `my_current_goal`, `my_own_claims`, `my_unresolved_questions`, `my_stance_toward_others`, `what_I_personally_witnessed`
- `candidate_common_ground_with[person]`: accepted-for-now referents, agreements, acknowledged differences, and their event sources
- `pending_sequences`: FPP id, projected recipient(s), expected class of action, status (`offered`/`candidate_response`/`clarification_requested`/`acknowledged`/`contested`/`withdrawn`), evidence IDs

Important: `candidate_response` is not proof of an *answer*, `acknowledged` is not proof a proposition is true, silence is not assent. A relevant denial, uncertainty, refusal, or even deliberate evasion can be an authentic second part with lasting consequences.

### 3. Arbitration *before* speech generation (MMAgents + AutoGen pattern)
Current workflow generates expression for all four and then publishes as many as survive checks. Replace **in a separate experimental branch** with:
```python
event = last_observed_public_action()
affordances = build_action_candidates(event, each_person_private_state)
if a_directed_first_pair_part_projects_response(event):
    candidates = addressed_or_invited_people(event)
    # People can accept, answer, decline, clarify, stall or redirect; not forced to comply.
else:
    candidates = [person for person in awake if person.wants_to_speak(affordances)]
next_speaker = resolve_floor(candidates, individual_readiness, relationships, recent_context)
if next_speaker is None:
    pause_or_allow_prior_speaker_to_continue()
else:
    action = next_speaker.choose_social_action(affordances)
    utterance = next_speaker.realize(action, local_evidence, partner_memory)
    commit_observed_turn(utterance)
```
**No arbitrary turn quota, no word blacklist, no deadline to change topics.** Hearing a question grants a conversational opportunity to the addressed speaker; it does not oblige cooperation. Allow genuine silence, minimal continuers, self-repair and two consecutive turns by the same speaker. Numerical readiness should be calibrated to data and must not be a disguised novelty score.

### 4. Grounding / repair / conceptual pacts (TRINDI, IBM, OpenDialog)
Update referent pacts separately per relationship: use a shortened name for a shared object if that pair has demonstrated successful uptake. Upon repair initiation, retrieve the **troublesome source utterance** (not an "alternate topic") and make clarification relevant. Only third-position acknowledgment or continued successful referencing gives provisional evidence of common ground. Revision updates the participant's own belief/stance and can alter their relationship without overwriting every listener's internal belief.

### 5. Bounded, evidence-linked memory (Generative Agents)
Retrieve on `(recipient, current action, unresolved sequence, referenced entities, own objective)`, *not* simply the most repeated terms. Log observations distinctly from reflections, link reflection to sources, and never let a reflection count as fresh independent support for itself. Do not quote `private_self.what_i_want` verbatim in public speech.

### 6. Keep the small text generator on the *last* step
The Room uses a quantized ~1B local generator in GitHub Actions. Let code supply the observed action, recipient, personal relation, and 1–3 relevant source lines; require little multi-party structural inference from a model that can fail at pragmatics. For ambiguous action types, evaluate optional higher-quality offline classifier or NLI before deciding that a misunderstanding occurred. The prototype regex-based action recognizer from PR #313 is only a preliminary heuristic, **not** a complete implementation of CA.

## Integration map against the current Room repository
- `scripts/room_interaction_sequence.py` (draft PR #313): retain as observer-scoped, explicitly uncertain recognizer; extend to action-pair status with evidence links and tests, not just '?'/regex.
- `scripts/room_group_dynamics.py`: preserve and enrich per-listener encounter, refusals, and revision records. Never broadcast information to absent agents.
- `scripts/room_engine_v5_core.py`: refactor `sense`/recurrent planning to separate action-recognition and readiness from utterance generation; remove `mandatory_speech` only after tests.
- `scripts/room_engine_v5.py`: route selected agent into existing speech realization; do not run all four expression calls and merely throw away outputs.
- `.github/workflows/sarah-society.yml`: current expression-node loop needs a selected-speaker path (run only one expression node, or an interface compatible with one); carefully preserve model boot, relay, timing, retry and offline semantics.
- `scripts/room_private_commit.py`: accept selected/valid subset of expressions and apply state updates only from published observations. Existing commitment/publish tests assume all nodes; explicitly migrate them in experimental isolation.
- `scripts/room_private_model_autonomy_legacy.py`: context supplies actual candidate actions and evidence. No target of being different, inventive, or word-diverse; phrase reuse and short acknowledgments allowed when interactionally appropriate.
- `scripts/room_expression_quality_legacy.py`: audit blanket minimum-length, mandatory novelty, and reject/retry protections. Keep privacy/security guards; remove only constraints contradicting legitimately selected social actions after validation.
- `room/cognitive_state.json` and `room/state.json`: add versioned action/uptake schema with backwards-compatible migration; never flush personalities or relationships merely to change topic.

## Evaluation with falsification, not superficial novelty
1. **Observe before modifications**: annotate at least 100 directed and 100 unsolicited sequences across actual Room transcripts, double-code a subset. Identify false positives in the action recognizer, conditional-relevance misses, unrelated third turns, missing repairs, refusals pursued, and premature assertions of understanding.
2. **Component counterfactual:** given the same event and each character's private state, verify floor selection offers Sarah the next turn after Mara asks *Sarah*, while allowing Sarah to refuse or clarify. A question to the group does not designate just one name. An absent character cannot volunteer based on events they never heard.
3. **A/B1** unchanged production vs action-aware floor selection only; same model, same starting snapshot, matched random seeds and external injected events, multiple runs. **A/B2** add repair/grounding state; **A/B3** add person-linked memory. Measure each mechanism separately.
4. **Primary outcomes**: question-answer relevance, repair resolution, appropriate receipt of refusals, continued use of understood referents, epistemic accuracy, and longitudinal relationship consistency. **Secondary**: lexical saturation and duration of cycles with no successful interactional accomplishment. Do not optimize type-token diversity or ban repeated phrases.
5. **Non-regressions:** privacy/identity boundaries, sleeping-entity scope, model timeout, warmth/humor/disagreement ability, self-selection, legitimate strategic repetition, and meaningful silence.
6. **Falsification:** if topic loops persist despite verified accurate selection and appropriate uptake, investigate (a) model pragmatic competence and (b) circular topic-state conditioning separately. If agents merely become silent or arbitrarily change subject, the intervention failed despite lower lexical repetition.
7. **Rollout:** only after unit, replay, shadow and blind human-rated tests; draft PR #313 stays unmerged until these show benefit. Preserve rollback via module toggle and state schema version.

## Research caveat
This note synthesizes tested components and observed implementations; it is **not** a claim that humans literally perform each software step or use 0–9 priority ratings. Timing, gaze, embodied action, overlap, uncertainty, coercion, and culturally variable norms are not fully represented by text. A deployed agent can approximate the *interactional consequences* of human conversational mechanisms, not reproduce all of human conversation from these sources.
