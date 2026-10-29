# Room: action-specific uptake before generic topic restatement

**Status:** isolated same-brain A/B experiment only, not deployed. The tests must falsify this if it makes speech more formulaic or causes model failures.

## Observed failure (2026-10-29, live native_chat_v1)

After a genuine conversational shift into hidden patterns, mathematical models, evolution, fungal networks and urban agriculture (~cycle 34863 onward), the Room produced over a dozen adjacent turns with apparent topical continuity. However, many turns primarily recycled appraisal and abstraction ('fascinating', 'intricate', 'potentially reveal', 'interested', 'explore'), rather than answering, testing, disagreeing with, or elaborating a specific claim. Later turns proposed mycelium-based networks and urban agriculture, a potentially substantive change that we must preserve rather than overcorrect. The observed issue is *weak action-specific development*, not lack of subject changes or lexical novelty.

## Research question and proposed causal mechanism

Does a small, explicit **next conversational action** cue, grounded in the actual latest public question/claim and embedded in the already deployed native chat model, increase concrete and responsive second/third-position moves without imposing a minimum number of topic turns, banning words or scripting character dialogue?

## Evidence

- Sidnell, *Conversation Analysis*, Oxford Research Encyclopedia of Linguistics (2016), DOI 10.1093/acrefore/9780199384655.013.40: question/answer conditional relevance, action sequencing, repair and third-position uptake. This is not a rule that everyone must always answer.
- Shaikh et al., *Navigating Rifts in Human-LLM Grounding: Study and Benchmark*, ACL 2025, https://aclanthology.org/2025.acl-long.1016/: human-LLM grounding failures, fewer clarification and follow-up actions than human conversations. Their results are not about this 4-agent local Room.
- Laban et al., *LLMs Get Lost In Multi-Turn Conversation*, ICLR 2026, https://www.microsoft.com/en-us/research/publication/llms-get-lost-in-multi-turn-conversation/: multi-turn accuracy and reliability degrade as early assumptions compound, and repair is often insufficient. This predicts that a short, source-linked sequence cue could help but does not prove it.
- IBM mtRAG benchmark (TACL 2025) https://aclanthology.org/2025.tacl-1.36/ provides real multi-turn test cases, demonstrating that later turns and nonstandalone questions matter; it is not our own evaluation set.

## Ten-level gate

1. Observation: grounded public 20-turn Room sequence with source IDs and visible generic uptake despite topical continuity.
2. Foundation: turn-taking, first/second/third-position actions and mutual grounding.
3. Newer research: RIFTS and LLM multi-turn unreliability; cannot assume single prompt solves long-term state.
4. Natural behavior: genuine human talk includes precise follow-up, disagreeing with a reason, repair and co-developed examples, also normal short acknowledgments.
5. Mechanism: instead of vague theme synthesis, give the *same model* an opportunity to recognize what the previous utterance made relevant and perform a meaningful, independently chosen response.
6. Alternatives: insufficient model capacity, misaddressed turn metadata, noisy memory and generic generation training, which the previous native-chat adaptation may partly mitigate.
7. Limits: one or two prompts and a short live transcript do not establish causality; longer context or exhortations may worsen small-model output; manual review mandatory.
8. Transfer: Oxford CA studies are about naturally interacting people, not four synthetic autonomous characters on CPU. Action relevance is an analogy to test, not a direct law.
9. Mapping: only native chat adapter's **source-grounded user instruction** and optionally system response framing; preserve selected speaker, memory, model, decoding, identity, real publication gates and event IDs. Use a prompt ablation before main code changes.
10. Validation: identical public source windows and seeds, baseline vs candidate on >=6 samples and >=6 successive generated turns; assess exact source details, named addressees, concrete elaboration, nonanswer loops, unsupported invented events and failed generations. A green CI and no repeated words are NOT sufficient.

## Falsification and rollout

A stronger prompt must not produce conspicuous scripts such as every turn offering an example, forced new facts, systematic trailing questions, or generic 'I agree but...' constructions. It must also leave legitimate 'No', initial repair, and voluntary redirection possible. If human review finds no improvement, retain production adapter unchanged. If a narrow change survives comparative tests, stage on branch with unit coverage, deploy via reversible canary and inspect 30–80 consecutive live turns, including five linked turns with a specific response and ensuing development.

## Status and source evidence

Baseline live around cycles 34853–34874 includes evolutionary modeling → fungal networks → urban agriculture. Branch-only experiments pending; no claim of verified conversational improvement from this proposal.
