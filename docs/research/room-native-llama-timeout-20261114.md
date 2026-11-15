# Room production inference timeout diagnosis (2026-11-14)

Status: proposed narrow reliability repair on a branch; live improvement **not yet verified**.

## Baseline evidence and context (research gates 1, 2, 3)

- Completed [Room runner 43571726383](https://github.com/maaronfanberg-lab/me-/actions/runs/43571726383), job 132377357669, contained **342** `TimeoutError: timed out` exceptions alongside **342** warnings that a named entity failed to act, and **50** scheduler rearming notices. Counts are from the retrievable job log, not simulated tests.
- Tracebacks originate in a blocking HTTP read from the loopback local model server while Concordia's simultaneous engine is invoking character actions.
- The production workflow launches Llama 3.2 3B with `llama-server ... -np 1`, while Concordia may schedule more than one character in the same step.
- Concordia's upstream [LanguageModel API](https://github.com/google-deepmind/concordia/blob/main/concordia/language_model/language_model.py) defaults to 60 seconds per request. The Room adapter passes this default to `urllib.request.urlopen`, capped at 90 seconds, while the workflow's native beat has an independent 300-second hard limit.
- The observed Room baseline at inspection: cycle **66,556**, silence **61 cycles**, `independent_life.completed_tasks=826`, current candidate rejected as semantic echo. State publication did not demonstrate conversational quality.

## Mechanism, competing explanations and limitations (gates 4–8)

A one-slot model server may queue multiple simultaneous requests; a queued request can hit its 60-second socket timeout even when the server and scheduler continue advancing. Raising the socket timeout **may** let more actions finish. This does **not** prove server contention is the sole cause. Long prompts, excessive generation, CPU speed, inference-server faults, unsuitable character instructions, semantic-echo filtering and missing social follow-through are competing explanations.

This is a transport/reliability change, not an attempt to imitate human conversation. Human turn-taking and relational evidence do not justify a particular socket timeout; transfer to humanlike dialogue must be evaluated separately. Failed actions should not be relabeled as voluntary social silence.

## Narrow implementation (gate 9)

- Preserve the existing 60-second default unless production explicitly opts in.
- Allow `ROOM_NATIVE_LLM_TIMEOUT_SECONDS` to set a bounded local-model socket timeout, clamped to 5–240 seconds.
- Configure **195 seconds** only for the native production workflow; preserve the existing **300-second external per-beat limit**, scheduler, state, memory, and publication filters.
- Test three cases with a mocked loopback HTTP response: no override=60, production override=195, overly large override=240.
- Entire repair is reversible by removing the one workflow variable or reverting this branch's commits.

## Required validation before claiming improvement (gate 10)

1. Confirm CI passes native integration and focused timeout tests on the repair branch.
2. On the next actual production runner using the merged revision, compare model timeout count per 50 native cycles with the logged baseline; inspect `acted_steps`, `native_publication_diagnostics`, task completions, and per-cycle duration.
3. Audit at least 50 new published conversation turns: proportion containing questions, direct responses to specific preceding assertions (including any new Allen turns), repeated intentions and verified action consequences.
4. Revert or adjust if timeouts do not decrease, if throughput collapses, or if dialogue quality worsens; neither successful CI nor fresh state is sufficient proof.
5. Never start a competing cognition runner just to validate this patch. Use the existing Pulse handoff.

Post-deployment result: **not yet observed**.
