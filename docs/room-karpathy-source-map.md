# Six Karpathy resources for the Room: source-verified engineering map

Prepared 2026-11-16 after reading the original repositories, their code,
and the original LLM Wiki gist. These methods do NOT demonstrate that any
repository provides human-like multi-agent relationships out of the box.

## Source-to-Room mapping

### 1. Autoresearch (highest immediate relevance)
https://github.com/karpathy/autoresearch
https://github.com/karpathy/autoresearch/blob/master/program.md

What it does: one agent changes a scoped training file, uses a frozen five-minute
training/evaluation budget, compares a stable validation bits-per-byte metric,
records keep/discard/crash outcomes, and repeats. The upstream evaluator in
prepare.py is frozen, even though the model code in train.py changes.

Room adaptation: freeze an identical simulation snapshot, model/version,
scenario, seed and evaluation procedure, change one experimental component,
then log the outcome with provenance. Keep failed experiments visible.
Never optimize speech frequency or a scalar proxy as if it measured friendship.
Do not copy the GPU training pipeline, automatic resets or open-ended access
to production.

### 2. nanochat (inference and evaluator architecture)
https://github.com/karpathy/nanochat

What it does: a compact pipeline from tokenizer and training to inference and
evaluation, with task modules and regression tests. Its README documents
model-training compute requirements. Room use: separate the quality of LLM
generation/formatting from scheduler, memory, world actions and social behavior;
run real end-to-end model-format tests and scenario-based evaluations. Training
a replacement GPT from scratch is not necessary or yet justified.

### 3. nanoGPT (older, for internal understanding)
https://github.com/karpathy/nanoGPT

What it does: minimal GPT pretraining and finetuning examples. The README
explicitly describes nanoGPT as old/deprecated relative to nanochat. Useful
for examining sampling, tokens and model internals when investigating local
model behavior; not a social architecture or preferred new training path.

### 4. LLM Wiki (persistent research knowledge, not executable software)
https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

What the original gist proposes: immutable raw sources, structured living
wiki, explicit schema/rules, ingest/query/lint processes, an index and an
append-only chronological log. Room use: a durable ENGINEERING knowledge
base recording hypotheses, experiments, failed fixes, evidence links and
contradictions; this should prevent repeated status-only rediscovery.
Apply the same provenance discipline to character memory but NEVER merge
a global wiki with the characters' private witnessed histories. The gist
is an idea file, not a drop-in memory service.

### 5. llm.c (independent reference checking)
https://github.com/karpathy/llm.c
https://github.com/karpathy/llm.c/blob/master/test_gpt2.c

What it does: LLM pretraining in C/CUDA with a reference CPU implementation;
its tests compare logits, loss and gradients against a Python reference.
Room use: compare deterministic decision and world-event transitions against
an independent referee oracle; require state invariants, not just green tests
or plausible-looking text. Do not rewrite the Room engine in C or import GPU
kernels.

### 6. micrograd (small correctness-first modules)
https://github.com/karpathy/micrograd
https://github.com/karpathy/micrograd/blob/master/test/test_engine.py

What it does: a minimal scalar reverse-mode automatic differentiation engine.
Tests compare its results and gradients with PyTorch. Room use: keep memory,
access-control, decision, causal-action and evaluation components small,
inspectable and tested against independent negative controls. No need to
introduce backpropagation into agent decisions.

## Implemented prototype; non-publishing

- scripts/room_social_trial.py is a new, original fixed-input A/B trial
  evaluator inspired by Autoresearch's frozen measurement discipline.
- To compare, both traces must declare the same pinned snapshot, scenario,
  input digest, model, seed and step budget, with all evidence lists present.
- It rejects private-event deliveries without witnessing permission, unknown
  visibility, duplicate event IDs and action claims with no referee-confirmed
  completion linked to the decision.
- A reply counts toward Allen-response evidence only if it identifies an
  accepted Allen input and matches the addressee. Zero speaking does not
  inherently fail because intentional silence can be legitimate.
- It compares transparent lexical repetition counters using
  scripts/room_social_eval.py, but never labels a model more human-like,
  never automatically merges code and never publishes state.
- CRITICAL TRUST LIMITATION: JSON world-event records must actually come
  from a trusted referee, not model-generated text. The current tool cannot
  independently attest their origin. Unstructured natural-language action
  claims also require future grounded annotation.

## Reproducible protocol for subsequent development cycles

1. Freeze a single Room snapshot, source Git SHAs, model/version, scenario,
   seed, input hash and maximum simulation steps. Preserve the original.
2. Register a specific falsifiable hypothesis and counterexamples, including
   privacy, false action, Allen-response and intentional-quiet controls.
3. Change just one module on a reviewable branch. Do NOT launch a second
   production writer.
4. Replay the same scenario with Concordia baseline and social successor,
   keeping the evaluator, referee and model fixed wherever feasible.
5. Capture generated actions, failures, published turns, evidence IDs, known
   deliveries, verified event receipts and resource use.
6. Reject unsafe/incomparable traces. A passing unit suite alone is not
   sufficient evidence of improved conversation.
7. Use blinded, complete-sequence review for social coherence, friendship
   continuity, differentiated character interests, replies, disagreement,
   recovered commitments, and verified action consequences.
8. In a chronological ledger, mark keep-for-testing, discard, or inconclusive.
   Maintain references and contradictions; never erase failed history.
9. Consider a single-writer production cutover only after independent
   behavioral verification, safe rollback planning and permission checks.

## First pre-registered scenario

From the same snapshot, introduce an acknowledged, public Allen question
directed at Sarah while she has an unfinished task. Verify that the task
survives, the question eventually gets a witnessed non-invented reply,
any claimed task completion matches a unique referee event, and no other
agent acquires private context. Counterexamples: a Mara-private message,
a duplicate event ID, an unsupported completion claim, and an empty/quiet
scenario. Record failures as prominently as successes.

## Attribution

All six references came from the user's provided list. The evaluator's
implementation is original and adapts the experimental methodology, rather
than copying upstream Karpathy code. Respect each upstream project's license
if code is incorporated in the future.
