# Question-contingent opportunities for knowledgeable Room participants (2026-10-29)

## Observation and hypothesis
In public Room published cycles **35201–35216**, an external shared community-garden event led to **16 consecutive concrete scene turns**, a meaningful improvement over previous abstract narrative loops. But all 16 were spoken by **Sarah, Mara or Jules**, with **Owen absent**, despite Owen privately holding relevant information that the garden's water-pressure gauge was unusually low. During question-driven exchanges about water pressure, the open-floor selector used hash tie-breaks and public turn provenance because separate model thought calls are disabled for CPU reliability. We hypothesize it can give better, humanlike reciprocal information transfer if a question creates an opportunity for a participant with an **unshared directly relevant fact** to speak, without compelling speech or rotating speakers by quota.

## Foundation / contemporary evidence and transfer caveats
- Sacks, Schegloff & Jefferson, 1974, *Language* DOI 10.2307/412243: locally sensitive turn allocations. It does not prescribe global knowledge-based auctions.
- Clark & Wilkes-Gibbs, 1986, *Cognition*, DOI 10.1016/0010-0277(86)90010-7: reference and mutual understanding depend on collaborative feedback and repairs.
- Tang, Mao & Suhr, EMNLP 2024, https://aclanthology.org/2024.emnlp-main.1100/: multi-perspective referential communication is challenging for models, and communicative success feedback has measurable gains. This motivates a test but does not establish success for an unsupervised four-character Room.
- Li et al., ACL 2025, https://aclanthology.org/2025.acl-long.1105/: sequence-aware role differentiation and cooperative roles can help collaboration, but their tasks differ from open-ended social dialogue.
- Peng & Shang, NeurIPS 2025, https://papers.neurips.cc/paper_files/paper/2025/hash/15294ba2dcfb4521274f7aa1c26f4dd4-Abstract-Conference.html: codified role logic may preserve character behavior even in small models, but controlled benchmarks do not imply naturalness.

## Mechanism / competing explanations
When the latest *real public participant* turn ends in a question with no exclusive audible addressee, and the bounded second-scene environment remains active, compare distinctive content words in that question with each character's own privately supplied observation. An unvoiced relevant fact adds a bounded **response opportunity score**. This is not a requirement to speak, a rotating speaker quota, a topic ban, or knowledge transfer to the selected model: only the selector reads each private fact, and the speaking model still receives its own fact only. A named recipient has absolute priority, sleeping people stay silent, and the same private fact does not repeatedly create priority after that person has spoken it. This approximates the human practice of relevant knowledge holders self-selecting to answer questions. Its main flaw is lexical overlap, which can miss paraphrases or reward accidental shared words; a specific scene may also explain results, and the scorer itself does not prove the character's actual answer is responsive.

## Phase-specific validation
A strict sequential phase separation avoids making two changes at once:
- Pre-state cycles **35200–35211**: first garden scene, salient environment cue only.
- **35220–35231**: second lantern scene with explicit witnessed-action feedback enabled, fact-relevance floor **off**.
- **35232–35243**: same lantern scene, action-feedback **off**, fact-relevance floor **on**. The scene is kept salient for an extra twelve beats so the only intended mechanism change is the floor. Note obvious order and carry-over confounds, so this is exploratory rather than causal attribution.
- Outside these windows, no additional floor score, no hidden-world cue after 35260.

Tests cover public vs private facts, question relevance, no-topic-word bans, user-address priority, sleeping speakers, answered-fact exhaustion, and disabled mode. Success requires not merely more distinct speakers but at least two observed questions answered using relevant details, another party taking up or challenging those details, and coherent multi-turn continuation. Failure includes surface name rotation, private facts leaking to wrong speakers, speculation replacing actual evidence, or no scene-relative response. Report the observed output, not only passing CI.

## Research gate summary
Observed issue established by published feed; original conversation analysis and newer role differentiation/reference research supply plausible mechanisms but not direct proof; competing hypotheses include model quality, scenario salience, and brevity of public context. Implementation is a bounded selector score in `scripts/room_conversational_floor.py`, with no change to model speech generation or public history; test with existing CI and live phase observations. Post-change validation: pending.
