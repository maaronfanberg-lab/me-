# Bounded generation retry for live self-perspective failure

**Status:** isolated patch, not yet deployed.

## Observed issue and baseline

GitHub live Room run 40791293144, 2026-10-29 ~00:02–00:03 UTC: selected Sarah and fallback Owen were both rejected with `RuntimeError: private Room publish quarantine for [entity]: self_perspective_leak` and two failed beats caused `unrealized_conversational_action`. The final publication gate correctly prevented incorrect role-identity text but generation did not retry that precise error, which was only detected during later candidate preflight.

## Research question

Can the already-present bounded three-attempt expression generation loop detect precisely that same known integrity error and retry, keeping final publication unchanged and without synthesizing dialogue?

## 10-level evidence gate

1. Observation: specific live run and error, with returned live source, not an inferred behavioral story.
2. Foundation: error detection before publication and repair after a failed production attempt; distinguish interactional repair from internal software retry.
3. Current evidence: compare existing production candidate validation and bounded model retry architecture; no outside claims about improved human behavior.
4. Natural behavior: this is not a conversational rule or word ban, but prevents public model role-description leakage.
5. Mechanism: the generator can inspect its own candidate, detect the same `self_perspective_leak` signal, and provide feedback to the next model attempt.
6. Alternative explanations: context corruption, weak 1B model, fallback to another speaker, repeated sampler failure; prompt repair may not succeed.
7. Limitations: a three-attempt loop cannot guarantee success; CI stubs test control flow, not actual model performance.
8. Transfer: this is a technical integrity fix, not a direct transplant of human conversation-analysis findings.
9. Mapping: add one narrow retry condition to `scripts/room_private_model_autonomy_legacy.py` *before* returning expression, preserve all preflight and commit checks.
10. Validation: deliberately produce one `I, Sarah` malformed output then a clean reply in a mock model boundary; check the second call is made and selected speech is preserved; require CI green, live beats after rollout, no unvalidated language publication.

## Rollback

Rollback if new loop stalls generation, increases failed model calls or compromises output integrity. Do not declare substantive conversational improvement from this technical fix alone.

## Outcome

Pending tests and live canary; no claim of sustained genuine responsiveness.
