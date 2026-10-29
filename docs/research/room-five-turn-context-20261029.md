# Five witnessed turns for a four-person Room: source continuity A/B

**Status:** isolated offline/real-model study. Not deployed, no conversation-state mutation. Change only bounded witnessed public context, not speaker rotation, content bans, mandatory topic length or scripted lines.

## Observable mismatch

The Room has four autonomous voices. Live selected-floor `sense` currently gives a character only the three most recent public turns (`room_engine_v5_core.py`), and native speech further clips that to three (`room_chat_speech.witnessed_context`). After three other participants speak, a character can no longer hear its *own* last published utterance or the initial concrete proposal five turns earlier. Recent live sessions developed a subject over 10–20 turns but repeatedly replaced specifics (fractal geometry, circadian rhythm, mycelium networks) with abstract 'intricate web', 'fascinating', 'hidden pattern' talk. The question is whether a full 4-person interaction cycle of public evidence helps.

## Research question

For identical witnessed windows, character identity, model and seeds, does **five** most recent public turns outperform three for substantive second/third-position response and concrete multi-turn development, with tolerable latency and no increased fabricated history?

## Foundational and current evidence

- Sacks/Schegloff/Jefferson (1974) show locally managed turn allocation; sequential actions can extend beyond adjacent utterances.
- Sidnell, Oxford 2016, DOI 10.1093/acrefore/9780199384655.013.40, describes non-minimal post-expansions, questions/answers and repair.
- Clark & Wilkes-Gibbs (1986) grounding and Brennan/Clark (1996) partner conceptual pacts: conversational contributions rely on shared recent history, not just topic-word overlap.
- Shaikh et al., ACL 2025 https://aclanthology.org/2025.acl-long.1016/ show grounding deficiencies in human–LLM conversation; larger public turn windows could help or confuse small models.
- Laban et al., ICLR 2026 https://www.microsoft.com/en-us/research/publication/llms-get-lost-in-multi-turn-conversation/ find substantial unreliability with multi-turn context; adding tokens may amplify mistaken assumptions and is therefore a hypothesis, not a fix.

## Ten-level gate

1. Observable problem: native speech currently clips every four-voice live sequence to three recent turns, verified in two code paths, alongside public repeated generic abstractions.
2. Foundation: sequence expansion, grounding and partner-reference continuity.
3. Current evidence: multi-turn reliability and grounding studies show complexity, not guaranteed benefit.
4. Natural behavior: participants can respond to one another after intervening turns, refer back, repair or change subject; no minimum continuity quota.
5. Mechanism: allow each model one full turn-taking cycle plus a spare turn, only from witnessed public text, without an invented synopsis.
6. Competing explanations: model capacity, prompt burden, stale memory, mistaken selected speaker, decoding and nondiscriminating generic praise.
7. Limits: five turns may overburden 1B and shift attention to irrelevant older text, increasing drift and latency.
8. Transfer: conversational findings from humans and dyads need verification in this specific 4-agent synthetic chat and CPU footprint.
9. Mapping: opt-in `ROOM_CHAT_CONTEXT_WINDOW=5` in core sense source selection and native `witnessed_context` clamp; existing expression `[-5:]` already fits, no changes to saving, identity or publication integrity.
10. Post-change: real Llama1B native A/B on >=8 identical public sample windows and six-turn continuations, manual action-specific review, identical seeds/decoder, CI including Allen and sleeping-agent filtering; do not deploy without positive evidence.

## Safety and rollback

No private or system records enter model context. Retain Allen accepted public text up to existing limit and sleeping participant filtering, preserve all public source IDs, no new speaker quotas or topic priorities. If five-turn context adds bland echoes or latency without substantive improvement, remain on three. Deployment, if justified, must require main-branch CI and a later 30–80-turn live review. Even a green check and no exact repeats do not prove natural dialogue.

Outcome: pending experimental results.

## Matched-seed real-model outcome: rejected for production

GitHub Actions run 40802013207 passed source/private/public-window tests and saved `docs/research/room-five-turn-shadow-20261029.json`. The three-turn and five-turn arms each returned 8/8 accepted single-case replies and six generated continuation turns. The five-turn arm failed to improve the human-inspected chain: it introduced unsupported physical stage directions ('I listen attentively ... nod thoughtfully'), speculative 'Fractal Entropies' and topic-only paraphrase. The three-turn chain was also weak. Widening the raw evidence window alone cannot be credited with substantive grounding; the extra context can distract the 1B model. Keep the live three-turn window; no merge. A richer independently verified compact sequence state remains a *future hypothesis*, not an implemented result.
