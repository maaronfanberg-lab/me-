# The Room: implementation plan at a glance
**Reviewed:** 2026-10-24 | **Status:** ready for isolated offline build and fault-injection, **not** live deployment.
**Authority:** full canonical specification in \`room-human-conversation-implementation-plan-20261024.md\`; six verified, independent-read-only Claude bridge consultations are linked there. Last two rounds identified **zero new critical/high specification blockers**, but code remains unimplemented and could have bugs.

## Purpose
Build social and conversation-analysis **mechanisms**, not a phrase repetition suppressor. Sarah, Mara, Jules and Owen should decide to speak or listen based on who addressed whom, open questions, uncertainty, repair, relationships and personal motivation. Intentional echoes, shared references and concise responses remain legal. A lower number of repeated words is not success.

## Work sequence

| Gate | Implement and test in isolated sandbox | Pass before continuing |
|---|---|---|
| 0. Reproducible baseline | Immutable Room state, 200 human-labelled action sequences, full rejection-predicate inventory, protected read-only replay, pinned 1B model/temperature with topic-label ablation. | No production credentials or writes, evidence labels and baseline quality rubric reliable, generation capability measured. |
| 1. Reliability first | Typed healthy-silence vs model-failure outcomes, heartbeat watchdog, Git-publication idempotency, safe ACK, durable relay journal, authenticated resync, mirror history pagination and backlog controls. | No public duplicates, lost accepted Allen messages, false healthy failures or false restarts in clock/crash/push/mirror tests. 20/50 queue and stale-200 cases simulated. |
| 2. Stop coercing output | Remove arbitrary "Distinct contribution", mandatory speech and context-echo novelty veto **only in experimental path**; preserve privacy and structure checks. | Short acknowledgment, repetition for repair and intentional callbacks pass end-to-end; prompt leaks and gibberish still rejected. |
| 3. Recognize actions | Observer-specific, source-linked candidate actions with uncertainty: directed/group questions, replies, misunderstanding, refusal, agreement, repair and third-position evidence. | Blind human validation; ambiguous addressees don't create fictitious certainty or global shared truth. |
| 4. Choose who speaks before generating | One social opportunity-based selector; addressed participant may accept/decline/repair; others may self-select; previous speaker may continue; everyone may choose silence. Generate only the selected person's output. | Group/targeted/silent counterfactuals and full old-system regressions; observer sleep/wake respected. |
| 5. Ground understanding and memories | Per-person shared reference pacts, open commitments, remembered interactions, third-position repair; retrieve evidence from the partner's actual witnessed experience, not repeated topic tags. | Source-traceable memory, no hallucinated agreement, continuity after reboot and conflict, no contamination of absent participants. |
| 6. Prove before deployment | Offline A/B with same frozen state/model/seed; B1 action floor, B2 move-aware speech, B3 grounding/memory, blind annotators and uncertainty intervals, canary copy and rollback. | Clinically/socially relevant improvements in genuine responsiveness/repair, without privacy, liveness, continuity or freedom-to-repeat regression. Approval required before merging. |

## Highest-priority failure tests
- Silence for longer than the existing 900-second watchdog vs repeated invalid generation: both are distinguishable.
- Allen queues 50 messages but only exposes oldest 20; durable Git acknowledgment allows the queue to drain while mirror recovery remains pending.
- Retry after Git push, before relay or queue ACK; no duplicate or changed public utterance.
- Git non-fast-forward with irrelevant metadata vs genuine new conversation; abandon stale unpublished generation safely.
- Mirror rejects legitimate newer feed with HTTP 200 \`accepted:false\`; only authenticated authoritative resync repairs it, never arbitrary force.
- 500-event relay outage, more than recent viewer window: every accepted event recoverable via paginated source-ID history.
- A valid repair echo ("Trees?") or response ("No.") must not be removed for lexical similarity or brevity.
- Observer-local memory: a character cannot remember turns that occurred while sleeping.
- Two consecutive adversarial reviews report no NEW high/critical plan blockers. Those reviews were **not tests**.

## Links
- [Full reviewed implementation specification](./room-human-conversation-implementation-plan-20261024.md)
- [Implementation precedents and research](./room-implementation-precedents-20261024.md)
- [Foundational conversation-analysis research record](./room-interactional-sequence-evidence-20261024.md)
- [Draft PR #313](https://github.com/maaronfanberg-lab/me-/pull/313)

**Deployment state:** No experimental code merged; production Room untouched. The next step is offline engineering with full fault injection and action-level evaluation, not another prompt-only patch.
