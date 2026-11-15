# Little World Lab — research gate

Date: 2026-09-05

## Observed problem / opportunity

The repository has Falcon/BitNet-backed agent work, but there is no fresh, isolated sandbox for testing sustained multi-agent behavior with 6–10 fictional agents, private memories, limited observations, environmental incidents, repeatable runs, and quantitative diagnostics. The goal is not to claim a valid model of human society. The goal is to build an instrument for observing whether a small local language model can sustain coherent, non-scripted agent behavior over time and to make failure modes measurable.

This experiment must remain separate from The Room, Emily/Olivia runtime state, and personal/family material.

## Research question

What is the smallest auditable architecture that lets language-model-driven agents perceive a grounded local world, retrieve private memories, choose structured actions, interact, and persist state without smuggling a predetermined story into prompts or allowing free-form model output to mutate world state directly?

## Sources checked

1. Park, J. S. et al. (2023), **Generative Agents: Interactive Simulacra of Human Behavior**, UIST 2023 / arXiv:2304.03442. https://arxiv.org/abs/2304.03442
   - Memory streams, dynamic retrieval, reflection and planning were all important in the authors' ablations.
   - The paper demonstrates emergent-looking coordination in a sandbox but evaluates believability rather than establishing that the agents are faithful human models.
2. Vezhnevets, A. S. et al. (2023), **Generative agent-based modeling with actions grounded in physical, social, or digital space using Concordia**, arXiv:2312.03664; current first-party implementation documentation at Google DeepMind Concordia. https://deepmind.google/research/publications/64717/ and https://github.com/google-deepmind/concordia
   - Separates entities, simulation engine, and a world/game-master resolver. Agents propose actions; the environment resolves what can actually happen.
   - Current Concordia documentation explicitly separates observing, scheduling, resolving, and terminating in the engine.
3. Gao et al. / Humanities and Social Sciences Communications (2024), **Large language models empowered agent-based modeling and simulation: a survey and perspectives**. https://www.nature.com/articles/s41599-024-03611-3
   - Highlights autonomy, social ability, reactivity and pro-activeness, while also emphasizing robustness, reproducibility, perception/action-generation errors, and the need for micro- and macro-level evaluation.
4. Larooij & Törnberg (2025), **Do Large Language Models Solve the Problems of Agent-Based Modeling? A Critical Review of Generative Social Simulations**, arXiv:2504.03274. https://arxiv.org/abs/2504.03274
   - Warns that generative ABM validation is often weak and that subjective believability is not operational validity. Black-box language models can obscure causal mechanisms.
5. Taillandier et al. (2025), **Integrating LLM in Agent-Based Social Simulation: Opportunities and Challenges**, arXiv:2507.19364. https://arxiv.org/abs/2507.19364
   - Emphasizes behavioral inconsistency, calibration, reproducibility, and hybrid architectures rather than treating LLM output as self-validating.

## Contradictory / limiting evidence

- Fluent or emotionally plausible dialogue is not evidence that simulated behavior is human-valid.
- More memory or more planning can increase coherence while also making the causal mechanism harder to inspect.
- Small local models may repeat themselves, ignore constraints, emit malformed structure, or converge on prompt-shaped stereotypes.
- Reproducibility is limited when real-model sampling is stochastic. Deterministic CI therefore validates engine invariants, not Falcon behavior.
- No v1 metric should be labeled a measure of consciousness, personhood, human realism, or social validity.

## 10-level gate

1. **Observed problem:** PASS. Missing isolated, testable multi-agent sandbox is directly observable from repository structure; current work is tied to other experiments.
2. **Foundational evidence:** PASS. Generative Agents supplies the memory/retrieval/planning precedent; classic ABM concerns require explicit state and rules.
3. **Current evidence:** PASS. Concordia's current architecture and recent surveys support modular environment resolution and explicit evaluation.
4. **Natural-behavior evidence:** PARTIAL / NOT CLAIMED. This v1 is not intended to reproduce a specific human population. Human-realism claims are explicitly out of scope.
5. **Mechanism evidence:** PASS FOR ENGINE DESIGN. Implement private observation, memory retrieval, action proposal, validation/resolution, state persistence, and measurable interaction. Do not implement canned social phrase lists.
6. **Competing explanations:** PASS. Apparent emergence may instead be prompt leakage, shared omniscient context, stochastic coincidence, or deterministic resolver rules. Logging and limited observations are designed to expose these alternatives.
7. **Replication / limitations:** PASS WITH UNCERTAINTY. Recent reviews identify unresolved reproducibility and validation problems; deterministic stub runs provide only software replication, not behavioral replication.
8. **Context transfer:** PASS WITH LIMITATION. We borrow architecture patterns, not conclusions about humans. Findings from this fictional sandbox do not transfer automatically to The Room or real people.
9. **Implementation mapping:** PASS. New isolated `experiments/little-world-lab/`; model backend abstraction; engine-owned structured action validation; private memory retrieval; local observations; JSONL event log/checkpoints; metrics; deterministic stub backend.
10. **Post-change validation:** PASS FOR SOFTWARE ENGINE; behavioral result pending a real Falcon run.

## Implementation mapping

- **Model boundary:** backend returns one JSON action proposal. It cannot modify world state.
- **World engine:** owns locations, incidents, action validation, consequences, scheduling, termination, and checkpoints.
- **Observation boundary:** each agent receives only its identity/goals, current location, visible co-located entities/resources, relevant private memories, and explicitly known facts.
- **Memory:** append-only private episodic records with recency, importance and lightweight lexical relevance scoring. No cross-agent memory sharing except through resolved observable events.
- **Relationships:** explicit numeric familiarity/trust state updated only by resolved interactions, not by prose sentiment guessing in v1.
- **Dialogue:** generated only as the payload of a valid `talk` action to a co-located target. No canned fallback dialogue.
- **Incidents:** change environmental state or observations; they do not dictate character responses or story outcomes.
- **Persistence:** JSONL event log plus JSON checkpoint sufficient to resume and audit.
- **Testing:** deterministic stub backend exercises engine rules without requiring Falcon in CI.

## Pre-change baseline

No isolated little-world experiment exists, so there is no comparable run baseline. The baseline for software behavior is therefore absence of the capability. The first stub run will establish deterministic engine metrics; the first Falcon run will establish a behavioral baseline for later A/B comparisons.

## Validation criteria

Software / CI success:
- same seed + stub backend produces the same event sequence;
- invalid or malformed model actions never directly mutate world state;
- agents cannot talk to non-co-located targets;
- agents do not receive other agents' private memories;
- incidents alter world state without prescribing dialogue;
- checkpoint/resume preserves tick, world state, agent memory and relationships;
- anti-loop logic prevents one repeated action from consuming the run indefinitely;
- event log is append-only JSONL and metrics can be recomputed from it.

Behavioral baseline criteria for later real Falcon runs:
- action diversity and pairwise-interaction graph are measurable;
- exact/near-exact utterance repetition is reported rather than silently hidden;
- environmental incidents can be traced to observations and later actions without giving every agent omniscient knowledge;
- multiple seeded runs are compared before calling a pattern 'emergent'.

## Post-change result

Implementation is complete for the v1 software engine. Eight local unit tests passed after the Claude-reviewed architecture changes. GitHub Actions workflow **Little World Lab smoke**, run #1 (`33988370970`), completed successfully on 2026-09-05: the unit-test step passed and the deterministic 12-tick smoke run passed with the expected 8 agents, 24 resolved actions, zero backend errors, and the expected log/checkpoint outputs.

The software gate is therefore satisfied. This validates the engine's deterministic test path and core invariants, not Falcon behavior. A real Falcon/BitNet behavioral run remains the next evidence step and must use a compatible model server; multiple seeded runs should be compared before describing any observed pattern as emergent.
