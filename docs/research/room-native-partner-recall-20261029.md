# Partner-specific recall in the native Room speech adapter

**Status: research-only, opt-in experiment. Production remains unchanged until source/privacy unit tests and live-model A/B justify it.**

## Verified problem

During 2026-10-29 native-chat rollout, `room_engine_v5._llama_model_run` computes `group_context` using `room_group_dynamics.model_context` (after verified memory relevance PR #342), but `room_chat_speech.messages` accesses only profile core identity, limited motives, presence and last public turns. It ignores that bounded, provenance-tagged group history and relationship state. Therefore the memory-relevance improvement to native conversational memory does not yet produce longitudinal partner-specific responses. This is an architectural gap, not proof that adding memories makes dialogue better.

## Research question

When the current public discussion precisely refers back to a prior partner-specific concept, can a **single** provenance-tagged, short, source-matched public quotation from the already retrieved `group_context.encounters` support genuine callbacks without distracting the model into arbitrary old topics?

## Sources and limitations

- Sacks, Schegloff and Jefferson (1974), turn-taking, adjacent and expanded sequences.
- Clark & Wilkes-Gibbs (1986), doi:10.1016/0010-0277(86)90010-7, grounding and collaborative reference.
- Brennan & Clark (1996), doi:10.1037/0278-7393.22.6.1482, partner-specific conceptual pacts and lexical entrainment. Referent-linked terms in human dyads are not unrestricted recitation of personal histories.
- PR #342 independent verified Claude consultation established that partner identity by itself admitted irrelevant memories, such as random variable X during species biology dialogue. Fixed by topic-first gating.
- ACL 2025 RIFTS (https://aclanthology.org/2025.acl-long.1016/) and Laban et al. ICLR 2026 (https://www.microsoft.com/en-us/research/publication/llms-get-lost-in-multi-turn-conversation/) document LLM grounding and multi-turn failures; neither proves any memory design improves this local 3B Room.

## Ten-level research gate

1. Observed issue: native adapter does not consume computed memory output despite extensive grounding work.
2. Foundation: grounding, source recognition, co-constructed partner-specific reference.
3. Contemporary: local Room's 1B copied quotes and drifted; naive context increase failed empirical A/B (run 40802013207).
4. Natural behavior: people revisit shared referents when relevant, not merely because that interlocutor once spoke.
5. Mechanism: source-linked verified prior quotation as optional evidence, not a fact or a command.
6. Alternatives: 3B may hold coherent topics without history; memory may distract, invent biography, or force unsolicited callbacks.
7. Limits: human pacts do not mean a lexical overlap count is semantic agreement; two-term filter is only conservative context selection.
8. Transfer: no automatic causal claim for synthetic agents, requires real-model paired A/B.
9. Mapping: optional `ROOM_CHAT_GROUNDED_MEMORY=1` inside native `messages`, max one witnessed quote of <=160 characters with exact public speaker, source id, validity status, awake participants and >=2 distinct non-generic terms shared with current public speech. Never promote quote to system instruction, never repeat protected model/private markers, never mutate persistence.
10. Validation: independent privacy/source tests, real 3B matched public fixtures including a plausible long-term callback, compare uptake and invented-history incidence, then live 30+ consecutive turns only if positive. Rollback flag and baseline default remain.

## Failure conditions

- If the model starts using remembered quotes to manufacture current events or paraphrases arbitrary old topics, reject.
- If a recalled statement appears as an instruction, a user-controlled prompt marker, an unverified secret or a private moment, reject.
- If no matched referents exist, preserve exactly the baseline prompt.
- A green unit test or exact topical overlap alone is not success. Never script dialogue or impose speaker quotas.

Outcome pending; no deployed change.
