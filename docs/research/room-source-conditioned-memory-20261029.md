# Room: source-conditioned partner memory without topic contamination

**Status:** draft PR #342; no deletion, redaction or overwriting of stored memories. Only the optional prompt-context projection changes.

## Observed deployment symptom and code-level cause

On 2026-10-29 UTC the public Room sometimes went from repeated species-evolution questions to random variable X and P(X=0.1) without visible justification. `room_group_dynamics.model_context()` previously admitted any memory merely if `speaker == current_partner OR target == current_partner`, even when topic word overlap was zero. This is a demonstrable *possible* source of drift; the live utterance does NOT by itself prove retrieval caused that specific model response. The separate Llama 3.2 1B experiments also generated irrelevant clinics with no prior memory context, so generator failures remain an independent explanation.

## Foundation and current research

- Clark & Brennan (1991), Grounding in Communication, https://web.stanford.edu/~clark/1990s/Clark%2C%20H.H.%20_%20Brennan%2C%20S.E.%20_Grounding%20in%20communication_%201991.pdf : common-ground work is joint and activity-dependent.
- Brennan & Clark (1996), Conceptual Pacts and Lexical Choice in Conversation, DOI 10.1037/0278-7393.22.6.1482, https://pubmed.ncbi.nlm.nih.gov/8921603/ : partners retain jointly negotiated ways of referring to particular objects, not every remark by that partner.
- Maharana et al. (2024), Evaluating Very Long-Term Conversational Memory of LLM Agents, https://aclanthology.org/2024.acl-long.747/ : long-range dialog reasoning is difficult even with retrieval.
- Chang & Chen (2026), When Users Don't Ask: Benchmarking Context-Driven Memory Retrieval in Conversational Agents, https://aclanthology.org/2026.findings-emnlp.1289/ : in-situ implicit memory retrieval remains difficult, and better retrieval alone does not guarantee better response quality.
- Verified Claude bridge consultation, read-only input `bridge/inbox/claude-consult-20261029-room-memory-relevance-001.json` and output `bridge/outbox/claude-consult-20261029-room-memory-relevance-001.json`: speaker-alone inclusion is a real topicality defect; recommend topic-first, at most one recent non-topical partner memory in ambiguous contexts. Claude did not run or inspect the repository itself; recommendations were grounded in supplied exact code snippet.

## Ten-level research gate

1. Observed transcript: unrelated callback appears after repeated topic question.
2. Foundation: conditional relevance and partner-specific common-ground referents.
3. Current literature: LoCoMo and LOCOMO-CONV highlight retrieval and actual response quality as separate measures.
4. Natural behavior: recall should sometimes support a previously established concept, without forcing callback whenever the partner speaks.
5. Mechanism: source-linked topical overlap occupies up to 3 optional memory slots before relationship background.
6. Alternative causes: weak small-model semantic interpretation, stale episode, multi-speaker switch, unexpected sampler; replay needed for attribution.
7. Limits: token overlap is a rough proxy, rare single-token references can matter, and a topical sounding quote can still be misleading.
8. Transfer: human conceptual pacts do not automatically imply any synthetic agent can apply them competently.
9. Implementation: keep all persistent encounters and relationships unchanged, admit overlapping memory first; then allow at most one recent (16-cycle window), non-topical partner background only when current topic is thin (<2 terms) or explicitly asks about past exchange.
10. Validation: verify real group dynamics and custom memory tests; review live 30-80 consecutive turns after rollout. Count spontaneous off-topic callbacks and proper source-linked references. Revert if ungrounded invented history or missed callbacks worsen.

## Hard acceptance and rollback

- Memory selection should not mutate persisted minds, rewrite historical speech, insert any artificial utterance, impose topic persistence, or block ordinary terminology.
- Preserve ability to discuss unrelated personal subjects, to ask for earlier exchanges and to make genuine callbacks.
- Maintain `remembered_speech_not_verified_fact` marker, stable source ID, and waking/sleeping restrictions.
- If the active runner continues inventing unrelated past events, do not call this a cure and do not add lexical blacklists. Record counterexamples for the next model/memory design.

## Study status

Regression checks passed on isolated draft; deployment pending. The independent Qwen 2.5 1.5B trial had 4/4 valid responses but an unrelated solar-cooking reply and drifting 5-turn chain. It is not a demonstrated replacement.
