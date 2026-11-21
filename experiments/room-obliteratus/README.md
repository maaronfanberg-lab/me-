# Room × OBLITERATUS: isolated concept-steering experiment

**Status: harness and synthetic contract tests only. No real-model or live-Room result yet.**

This is a strictly off-by-default, read-only research experiment. It does not import, alter, deploy or publish the Room, touch live memory/state/feed files, or edit model weights. Its goal is to test whether a **validated, non-refusal concept direction** changes synthetic conversational responses when injected via OBLITERATUS v0.1.4's **reversible** `steer` hook. It explicitly does not use refusal/guardrail removal.

## Why this is a distinct experiment

The production Room's quantized `llama3.2-3b` GGUF runtime is not a drop-in target for this Hugging Face transformer activation-intervention API. The trial requires a separately downloaded, **dense**, compatible local Hugging Face model, its matching tokenizer, and an extracted, gate-validated, model-identity-matched `ConceptDirection` pair (`.safetensors` plus `.json`). The local model may be smaller than the production model; this is **not** an experiment on the actual Room model unless those architectures and weights match. Do not claim transfer otherwise.

The supplied exact release is OBLITERATUS v0.1.4, commit `461ff086e675d93969bbd7c99c53505762452309`. The GitHub release reports the ZIP SHA256 as `e2d0fb696b8cd025124e6d7cc69bbd8b7d969adc0f019697cb2a5dd6696eba99`. Download and verify the archive independently before installing; the archive was not fetched in this development environment.

## Prepare (manual, isolated research environment)

1. Install OBLITERATUS from its **verified v0.1.4 source** using the upstream installation instructions. Do not use the live Room environment. Use Python 3.11 or an upstream-supported version.
2. Create a new research concept pack using `obliteratus concepts init ./conversation-initiative --id conversation-initiative`. Replace every example with independently authored positive, neutral, and semantic-confound dialogue examples; include licenses and file hashes as specified by `docs/CONCEPT_PACKS.md`. Do not use private Room dialogue or internal character prompts. Split train/held-out data. Validate with `obliteratus concepts lint ./conversation-initiative`.
3. Extract and validate a direction using `obliteratus concepts baseline ./conversation-initiative /path/to/local/dense/model --output-dir /tmp/initiative-direction` (consult upstream help for exact model resolution). **Only a pass/warn gate** with a matching model id/commit, concept id and pack hash is accepted. No gate override.
4. Run the experiment using the same local dense model and direction:

```bash
python3 -m unittest discover -s experiments/room-obliteratus -p 'test_*.py' -v
python3 experiments/room-obliteratus/ab_trial.py \
  --model-dir /absolute/path/to/local/dense/model \
  --model-id EXACT_MODEL_ID_IN_DIRECTION \
  --model-revision EXACT_SOURCE_COMMIT_IF_PRESENT \
  --direction /tmp/initiative-direction/direction.safetensors \
  --alphas 0,-0.5,0.5,1 \
  --device cpu \
  --out /tmp/room-obliteratus-ab.json
```

For models requiring more than available CPU RAM, run on an isolated GPU machine and use `--device cuda`; this project does not provision one. `--model-revision` may be omitted only if the direction does not record a source revision. No network is used by `ab_trial.py`; model loading is local-only.

## What the experiment measures

Twenty independent **fictional** cases cover addressed response, misunderstanding repair, optional silence, avoiding invented memory, topic transitions, and repetition. Each is run with identical input and greedy decoding under pristine weights, four steering strengths, and pristine weights again after hooks are removed. The script **fails** if either the zero-dose placebo or the final unsteered outputs differ from the original; changed outputs alone never establish an improvement. Metrics include silent count, verbatim four-gram reuse, mistaken speaker prefix, question count, and response length. Full responses and SHA256 provenance are recorded to local JSON outside the repository. **These heuristic counts are not a naturalness score.** Results require blind ratings, multiple seeds/contexts, independent held-out conversations, and a collateral safety battery before any deployment consideration. Do not expose real users to untested steering.

## Limitations

- No model-based inference has been completed; 38 unit tests only validate harness control flow, input validation, and restoration reporting.
- No claims about subjective states, agency, empathy, or human equivalence follow from a direction or a single-turn response change.
- This runner does not implement OBLITERATUS's full 320-pair safety/collateral battery, or an independent evaluation of the specific concept direction; use the upstream gate and separate safety battery for those.
- It does not test longer-run Room memory, five-participant coordination, hallucination, privacy, or genuine live autonomy.
- Keep production's safety, witness, provenance, and publication gates intact. No auto-deployment, Actions write permission, or hourly job is added.

Research record: `docs/research/2026-11-16-room-obliteratus-protocol.md`.

## Round 2: executable research controls (November 16, 2026)

The 20 fictional situations cover all five speakers and include self-repair, direct address, uncertain memory, silence, topic transitions, source grounding and repetition. Added paired-change metrics, byte-identical zero-dose placebo and restoration controls, fail-closed generator output bounds, hook-cleanup tests and repeatable blinded pair preparation. There are **38 dependency-free unit tests** (six original plus 32 new). A simulated generator exercises the orchestration without loading a model; it is labeled not neural inference and not OBLITERATUS.

To run the simulator and make 60 unlabeled comparison pairs (no one has rated these yet):

```bash
python3 experiments/room-obliteratus/mock_trial.py --out /tmp/room-obliteratus-simulated.json
python3 experiments/room-obliteratus/blind_review.py \
  --report /tmp/room-obliteratus-simulated.json \
  --packet /tmp/room-obliteratus-blind.json \
  --key /tmp/room-obliteratus-secret-key.json
```

The answer key must not be shared with blind judges. The GitHub Actions job uploads **only** synthetic reports and unlabeled comparisons, not the local answer key. No real-model, safety-collateral or ecological-validity claims are made.

See `docs/research/2026-11-16-room-obliteratus-round2.md` for the 20-step evidence record.
