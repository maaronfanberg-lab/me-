# Endogenous Room: verified improvements and remaining validation, November 5, 2026 (UTC)

## Evidence, not promises

This research branch is a replacement architecture for an autonomous multi-character Room. No production Room runner imports this code, and **no live character, visitor turn, memory, or public feed was changed by these trials**.

### Previously observed failure

The original private-action generator repeatedly selected `reflect`, including when a character was directly addressed, and failed to commit new private beliefs. It satisfied JSON format but did not demonstrate meaningful agency. Its release gate remains blocked.

### Replaced the action-label trap with real proposed speech

- [Pinned Llama 3.2 3B free-speech pilot](https://github.com/maaronfanberg-lab/me-/actions/runs/41958332360): **6/6** source-validated natural speech proposals, including a concrete response to an addressed visitor. Not proof of sustained naturalness.
- [Extra interest/silence scenarios](https://github.com/maaronfanberg-lab/me-/actions/runs/41959056419): **9/9** valid speech, **zero voluntarily silent**. This demonstrated an over-talking problem despite a silence option.
- [Two-stage self-endorsement](https://github.com/maaronfanberg-lab/me-/actions/runs/41959748728): **5/5** valid decisions on the agent's *own specific draft*. Four YES and one NO. Owen chose not to interrupt a question directed to Jules. Validated self-chosen silence without a rotation rule.
- [Grammar-constrained Llama /completion](https://github.com/maaronfanberg-lab/me-/actions/runs/41960369854): **10/10** valid strict private JSON proposals with **six** voluntary spoken drafts, replacing earlier malformed mixed-quote outputs. Private belief revisions were **zero** in this run; do not infer self-development from format success.

### Model-authored goals

- [Real private-growth test](https://github.com/maaronfanberg-lab/me-/actions/runs/41960282029): one independently proposed, source-linked personal goal was accepted. That goal supported a later model-generated speech opportunity **without a new public event**. One attempted belief-revision was rejected by the validator; the model did not produce a recognized private belief change in this first run. Speech wording differed before and after the goal was introduced, but the result is not sufficient to isolate causality statistically.
- A later diagnostic found the model used the ordinary first-person expression `My hypothesis...`, which the validator incorrectly rejected when it expected `I...`. The parser has been fixed and regression-tested, while real-model repeatability remains under evaluation.

### New direct evidence for private-state causality

- [Real belief-and-goal replication](https://github.com/maaronfanberg-lab/me-/actions/runs/41962345800): model-authored personal goal **accepted**, private hypothesis **revised and stored**, follow-up speech changed, and another self-initiated contribution arose without a fresh public event. This replicates the successful [earlier run](https://github.com/maaronfanberg-lab/me-/actions/runs/41961813520), though sampling variation still limits quantitative causal claims.
- [Deterministic A/B/A test](https://github.com/maaronfanberg-lab/me-/actions/runs/41962408863): the same public conversation and model settings produced identical speech in the original private-belief state **A** on both repetitions, while changing only the private belief to **B** changed the answer. All **3/3** outputs were provenance-valid. This is controlled evidence that supplied private state can influence public speech in this one test, not proof of genuine human-equivalent agency.
- The research Room heartbeat now offers each participant a budgeted, individually owned private-cognition opportunity. A model may independently say `[NO_GOAL]` or `[NO_CHANGE]`; neither creates an artificial state transition.

### Crash and concurrent-run integrity

- `room_endogenous_transaction_store.py`: file-lock + revision guard, fsync and atomic rename, stable publication outbox IDs, consumed-bid deduplication, exact preservation of visitor messages.
- `room_endogenous_shadow_beat.py`: bounded private draft, same-character endorsement, genuine silence, a single selected candidate, and an uncommitted public-outbox message. Duplicate research cycles do not regenerate random speech. Replayed cycles reject new or altered visitor content.
- This is a **research-only** committed candidate state. It is *not* an integrated live Room publisher and does not establish exactly-once publication into the separate live feed without a separate acknowledgement protocol.
- **108 research-specific unit and synthetic-integration checks** are included in the existing Room conversation CI workflow, with green runs, alongside the older Room regression suite. The long-form 3B simulation is a separate experimental canary.

### The necessary remaining checks

Human-likeness and reliably endogenous progression require sustained, held-out multi-character dialogue, reliable source-supported private belief revisions across independent runs, and blind evaluators. The CPU budget cost of two separate model inferences (draft plus endorsement) must also be weighed against naturalness. No model-generated statement about completed physical actions may be treated as a witnessed event.

**Do not equate removing technical blockers with disabling provenance, privacy, visitor-message, rollback, or truthfulness protections.** The release gate is an empirical condition, not a switch to be hidden or deleted.
