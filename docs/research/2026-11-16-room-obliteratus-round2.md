# Room / OBLITERATUS v0.1.4: 20-step isolated research continuation

Date: 2026-11-16 UTC. Branch: `research/room-obliteratus-v014-20261116`. Draft PR #417.

## Research-only status

**No OBLITERATUS library execution, pretrained model inference, concept extraction, safety-battery run, or real Room modification is claimed in this round.** The 20-step sequence builds and validates the controls needed before a separate genuine dense-model trial. A deterministic fake generator is explicitly marked `NOT_NEURAL_INFERENCE: true` and `NOT_OBLITERATUS: true`; it cannot prove conversational improvement. The local Python unit-suite is evidence about program logic, not about AI cognition.

## 20 independently verifiable steps and outcomes

1. Verified that draft PR #417 exists and targets `main` from a separate research branch. **PASS**.
2. Verified the original GitHub Actions run `43883486892` completed successfully. **PASS**, original six checks only.
3. Reviewed the PR's modified files and verified production Room paths were not part of the experimental diff. **PASS**; new CI reinforces this with a git-diff allowlist.
4. Confirmed upstream OBLITERATUS `v0.1.4` source identity `461ff086e675d93969bbd7c99c53505762452309` from its release metadata. **PASS for metadata**; ZIP bytes NOT downloaded or independently hashed.
5. Inspected `v0.1.4` tag-locked `docs/CONCEPT_WORKFLOW.md`, `docs/CONCEPT_INTERVENTIONS.md` and `obliteratus/concepts/intervention.py`. **PASS**; use `steer` as a removable runtime hook, not weight surgery.
6. Rechecked model compatibility: current Room's `llama3.2-3b` GGUF is not a directly supported dense Hugging Face checkpoint for this harness. **CONSTRAINT RECORDED**, not worked around by pretending it is the same model.
7. Reran the original six local dependency-free tests before any edits. **6/6 PASS**.
8. Enlarged the independent fictional dialogue suite from six to 20 scenarios. **DONE**; all are explicitly invented, not gathered from Room users.
9. Verified the synthetic suite includes Sarah, Mara, Owen, Jules and Allen. **PASS**; no production persona prompts or memories copied.
10. Added strict input and bounded-response tests to reject unknown voices, extra private-state fields, malformed lines, overlength outputs, duplicate IDs or missing cases. **PASS in local contract tests**.
11. Made the alpha=0 placebo dose obligatory and compared it byte-for-byte with the pristine model's text. **PASS on simulator**; real model remains untested.
12. Retained pristine model comparison after every intervention dose, to catch hook leakage or baseline drift. **PASS on simulator**.
13. Made any placebo or restoration mismatch a recorded, fail-closed control failure. **PASS**; separate negative tests deliberately produce both failures.
14. Added per-case paired response-change and silence-transition measurements rather than comparing only aggregate proportions. **PASS on simulator**; not a causal-quality score.
15. Retained measurable four-gram repetition, literal last-line echo, question rate and word counts. **PASS**; no unsupported claim that metrics establish naturalness.
16. Added explicit speaker-prefix contamination checking, together with 20-case bounds. **PASS**.
17. Tested that the context manager removes an intervention even if generation raises an exception. **PASS on simulated hook**; real OBLITERATUS removal is still untested.
18. Executed the deterministic simulated trial on 20 scenarios across four doses; every placebo and restoration control passed. **PASS**, simulator only.
19. Generated 60 randomized, unlabeled answer-comparison tasks for a future blind quality review, with a separate local answer key. **PASS**; no actual judges or ratings yet.
20. Extended the branch-only GitHub Actions workflow to enforce permitted changed paths, rerun all contract tests, generate mock outputs and upload only safe synthetic artifacts. **PASS:** after two diagnostic CI failures caused by a moving-main comparison, the actual fork point was pinned, and run [`43886885051`](https://github.com/maaronfanberg-lab/me-/actions/runs/43886885051) passed all jobs.

## Baseline and effect status

- 20 synthetic prompts are ready, but **zero real neural-model responses** have been collected in this round.
- Data-generating concept pack, independent held-out validation and dense model weights are not yet present. A positive or negative `alpha` changed the deterministic **fake** generator by construction; this is not evidence that steering works in a language model.
- Deliberately added the alpha=0 test because the prior six tests checked restoration only, and an anomalous zero-dose arm could otherwise masquerade as intervention impact.
- Stronger activation interventions can degrade utility and coherence. See Xu et al., *Why Steering Works: Toward a Unified View of Language Model Parameter Dynamics*, ACL 2026, DOI: 10.18653/v1/2026.acl-long.1463, https://aclanthology.org/2026.acl-long.1463/.

## GitHub verification (confirmed on GitHub Actions)

- Original round-2 commit SHA: `255b09b7aa52275727e820ef7667b8ffeac4cc78`.
- First round-2 CI run: `43886451247`, **FAILED** at branch isolation; root cause was comparing against moving `main`, not a research-only diff. This was a test-design mistake, not a failed model experiment. Fixed by pinning fork-point `1ed9db726c9bee47846a182e2a7103105d689a39`. The corrected run and its results are recorded below.
- Corrected GitHub Actions run: [`43886885051`](https://github.com/maaronfanberg-lab/me-/actions/runs/43886885051), **SUCCESS**. All 38 tests passed in 0.047 seconds. Synthetic 20-case demo passed; 60 unlabeled pairs generated, without collected ratings. Uploaded artifact ID `14233374439`, SHA256 `601776cc002ce473c42ca266fac8cacdcfe193874daf4c3b2bb773509a3dcf7a`.
- Unit tests: 38/38 pass in local Python. Mock controls: pass. Anonymous task count: 60.
- The live Room's code/state/feed/prompts, deployment, and schedules have not been modified by these research changes.

## Next scientific gate

Fetch and verify the exact source archive, build and lint independent positive/neutral/semantic-confound concept packs, extract and validate a direction on a suitable *separate* small dense model, run non-refusal dose comparison, and evaluate collateral safety plus held-out and blind naturalness. Keep the trial in the research branch unless model-backed evidence justifies a separate promotion decision.
