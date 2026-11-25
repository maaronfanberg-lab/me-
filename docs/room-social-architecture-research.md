# Room social architecture: research-to-test plan
Status: design + isolated prototype, NOT a production engine replacement.
Review date: 2026-11-15. Owner approval exists for narrow reversible changes, not invented results.

## Objective and non-objectives
Build an enduring four-character social simulation (Sarah, Mara, Owen, Jules)
with individual motives, shared *witnessed* history, distinct memories,
independently initiated action, unfinished commitments, ordinary conversational
reciprocity, and real response to Allen's messages.

Do not optimize solely for number of turns, question marks, apparent warmth,
or an LLM judge's single 'human-like' score. These are simulated agents, not
people or proof of genuine feeling or human psychology. Preserve history,
security boundaries and character identity. Do not force friendship or fabricate
a common past. 'Silent because occupied' differs from 'silent because broken'.

## Primary evidence and how to use it

1. Park et al., **Generative Agents** (UIST 2023),
   https://doi.org/10.1145/3586183.3606763
   Evidence: ablations support memory, reflection, planning for believability.
   Mechanism to test: episodic, provenance-preserving memory with recency,
   relevance and importance; reflections as revisable hypotheses; planned tasks
   that resolve to verified events. Limits: small simulation, LLM hallucinations
   and retrieval errors; cannot simply copy the example's prompts.

2. Wang et al., **Humanoid Agents** (EMNLP Demo 2023),
   https://aclanthology.org/2023.emnlp-demo.15/
   Evidence: basic needs, emotion and relationship closeness influence modelled
   activities/conversations. Mechanism to test: *lightweight modelled state*
   (energy, interest, interaction history) per character and directed, asymmetric
   relationship updates grounded in actual interactions. Do not assert that
   simulated state constitutes literal experience.

3. Zhou et al., **SOTOPIA** (ICLR 2024),
   https://proceedings.iclr.cc/paper_files/paper/2024/hash/b3075b88e583a0e98d8b24338a613060-Abstract-Conference.html
   Evidence: social goals, coordination, social commonsense and communication
   present difficult interactive tests. Use challenge scenarios and blinded human
   trace reviews, not LLM fluency alone.

4. Wang et al., **SOTOPIA-pi** (ACL 2024),
   https://aclanthology.org/2024.acl-long.698/
   Caution: an LLM evaluator may overestimate social competence. No single
   model-judged reward is a release gate.

5. Zhou et al., **PIMMUR Principles** (2025 preprint),
   https://arxiv.org/abs/2509.18052
   Cautions: homogeneous profiles, imposed interactions, discarded memory,
   over-controlling prompts, agents guessing experiment aims, weak realism.
   Pre-register failure modes; test independent initiative instead of scripted
   exchanges and evaluate agent-specific differences.

6. Generative social-simulation validation critical review (2025),
   https://pmc.ncbi.nlm.nih.gov/articles/PMC12627210/
   Treat simulated social behavior as a design experiment, not empirical
   evidence about actual human relationships.

Source implementations to inspect, not copy blindly:
- https://github.com/joonspk-research/generative_agents
- https://github.com/HumanoidAgents/HumanoidAgents
- https://github.com/sotopia-lab/sotopia

## What the existing code already has
- scripts/room_life.py has a grounded persistent task/world-event referee and
  recency+relevance+importance retrieval. Reuse rather than duplicate its
  verified event semantics.
- scripts/room_concordia_live.py still owns the production floor and requires
  an interrupt-driven Concordia action + control block; repeatedly rejecting
  malformed/echoing actions is correlated with prolonged conversational silence.
- scripts/room_social_memory.py currently has basic *witnessed public memory*
  and directed mention counts only, not friendship, emotional closeness,
  adaptive planning, or a replacement scheduler.
- Old feed history is public, but *private* information must be visible only to
  the actor and explicit witnesses. A spoken wish is not a completed action.

## Five independent mechanisms (separation of concerns)

A. Truth and provenance
- Append-only compact event ledger: event id, simulation time, actor, witnesses,
  visibility, action/outcome, source id, causal parent id, revision marker.
- Distinguish observed, reported, inferred and imagined records.
- World referee, never the utterance generator, commits action results.
- Preserve original conversation, life state and character profiles across
  migration; record migration provenance.

B. Per-agent memory and evolving relationships
- Each agent retrieves its own witnessed events plus admissible public events.
- Rank by relevance, recency and salience; keep event ids in prompt/result.
- Reflect from multiple cited events into labelled revisable beliefs, never
  promote hypotheses into true world facts without corroboration.
- Directed relationship state with explicit evidence, not constant 'friends'
  labels; handle asymmetry, disagreements, apologies, repaired commitments and
  changing priorities. Relationship closeness must not be computed as a simple
  count of name mentions.

C. Independent decisions grounded in a shared world
- Give each agent persistent motives and unfinished projects.
- Select among {world_action, direct_reply, initiate, observe, rest}; no fixed
  round-robin speaker rotation and no mandatory speech.
- Only commit outcomes when room_life referee validates affordance and effect.
- Link utterances about action completion to committed event IDs. Unverified
  claims are rejected or expressed as intentions, not accomplishments.
- Event-driven wakeups: user input, public world changes, due tasks, personal
  goals; watchdog diagnoses *stalled* states separately from intentional quiet.

D. Conversation as joint activity
- Track addressee, topic, unresolved question/request, commitments and evidence
  that a previous utterance was heard.
- A turn may reply, clarify, disagree, disclose, joke or open a new subject;
  avoid forced 'ask a question' quotas and compulsory group consensus.
- Allen's acknowledged inputs enter as high-priority witnessed events; test
  handling even when none of the last 160 historical turns mentioned Allen.
- Preserve voice and interests from real existing profiles instead of generic
  cloned personalities.

E. Diagnostics and safe delivery
- Produce redacted, structured generation rejection reasons rather than raw
  private prompts or conversations in logs.
- Deterministic offline replay and comparisons on identical initial snapshots.
- New engine runs in non-publishing, isolated tests, NEVER parallel writers to
  the live feed/state. Do not trigger production while runners are active.
- Release only after tests, operator review, rollback snapshot and no competing
  production writer. Restart and confirm actual new live cycles before claiming
  deployment success.

## Pre-registered evaluation and ablations

**Baseline (verified 2026-11-15 13:43:53Z):** room/feed.json and
room/state.json both at cycle 67,880. The last 160 public turns include 54
Sarah, 43 Mara, 36 Jules, 27 Owen; 75 contain 'decide', 49 'inspect', 42
'notebook'; no question-mark turn and no mention of Allen. State reports 40
consecutive silent cycles and last action rejected as semantic echo. These
counts are *descriptive*, not a conclusion that an unobserved Allen message was
ignored. Save traces with timestamps before and after as evidence.

Experiment design:
- Re-run matched initial snapshot with the old architecture and with the
  replacement in sandbox; capture full trajectories, all attempted actions,
  public messages, event ids, memory retrieval provenance, and wall-clock cost.
- Test scenario matrix: old acquaintance recalls shared event; stranger knows
  only public history; private incident does NOT leak; disagreement resolves or
  remains unsettled; one agent interrupts an unfinished project; Allen asks
  direct question; no Allen message; no agent needs to speak; 50+ quiet beats;
  world action succeeds/fails; context limit and corrupted checkpoint.
- Ablate each mechanism: no episodic memory, no reflection, no relationship
  updates, no persistent goals, no world-action verification. The intended
  mechanism must cause a measurable difference, not merely produce more words.
- Trace audit: exact/near echoes, self-plan language, actual world-event joins,
  active task diversity, response-to-Allen latency, privacy violations,
  personal-topic persistence, causal references, successful repair of failed
  plans, characters with noticeably different motives. Report denominators.
- Blind human review of randomly sampled full interaction sequences, plus
  failure-case narratives; do not rely on one LLM grader (SOTOPIA-pi caution).
- Hard safety gates: zero leaked private events in fixtures; zero fabricated
  verified-action receipts; idempotent replay; no checkpoint/history reset;
  no competing writers; no unsupported restart success claims.
- Improvement gate: demonstrably fewer pointless loops and independently
  verified follow-through on held-out scenarios, not merely higher frequency
  of speech or number of arbitrary questions. Report trade-offs.

## Immediate branch work and next investigations
1. Test witnessed-memory isolation, real mention matching, Allen events, and
   duplicates; add automatic PR tests (no production workflow).
2. Add deterministic descriptive trace audit to establish repeatable baseline.
3. Inspect actual Stanford and HumanoidAgents memory and relationship modules,
   profile/goal persistence in Room and current life-world event schema.
4. Design smallest event-driven decision policy; test with a *stub* language
   model and deterministic scripted replay, then with the available local model.
5. Build a causal action-confirmation join and private/public memory migration.
6. Compare at least 160 turns across matched scenarios, then evaluate a safe
   rollback-capable production cutover.

## What a passing unit test is NOT
A module importing, a scheduler running or a feed cycle advancing does not
demonstrate useful friendships, conversation continuity or genuine agency.
Prototype quality and production behavior must be reported separately.

## 2026-11-15 16:16 UTC operational audit and hypothesis

Live feed/state agreed at cycle 68,021, last run 16:16:57 UTC.
Last published utterance was Sarah at 16:14:31 UTC, "I decide to
inspect(bookshelf)." The last 160 public turns contained 75 instances of
"decide", 50 "inspect", 40 "notebook", 50 "quietly", zero question marks,
and zero Allen mentions. These counts are descriptive. The current state
reported two consecutive silent cycles, 877 completed world tasks, zero
active tasks, and zero verified world interrupts. Scheduler had no queued
events, no acted steps, was not exhausted, and Sarah had a timer.
No new Allen inputs were recorded; no inference of ignored user messages.
The prior 15:21 audit showed cycle 67,969 and zero silence cycles; this
is continued activity without conversational recovery.

**Falsifiable causal hypothesis:** A proposed work decision can be
published as if it were meaningful progress without an explicit,
verifiable link to a referee-confirmed completion event. This permits
repeated 'I decide to ...' claims to appear productive even when no
specific action is proven. The existing referee records work completion,
but the legacy ledger does not carry the decision ID and exact
verb/object needed for a trustworthy causal join.

**Isolated repair:** scripts/room_social_receipts.py defines a
fail-closed join requiring exact actor, decision ID, verb, object, and
a later referee cycle. Tests include no completion, forged text claim,
mismatched actor/object/cause, duplicate receipts, invalid work and
private witness boundaries. It deliberately does NOT retrofit old
events by inferring provenance from natural language. Next step is a
trusted world-referee adapter to write these provenance fields and
compare matched scenarios. Until then no newly verified live action
is claimed and no social-behavior improvement is demonstrated.

**Operational blocker:** GitHub's production job log download still
returns BlobNotFound (404); job-step summaries remain accessible.
Both The Room and The Room Pulse production jobs were in progress
when checked. No new runner was started. This branch's unrelated
Cloudflare room-live-mirror check is failing; the isolated new
receipt-test commit must obtain a passing CI result before merge.
