# Room × OBLITERATUS v0.1.4: isolated concept experiment

STATUS: Harness only; no validated real-model inference or live Room deployment.

This research-only tool uses reversible activation steering on a separate *dense Hugging Face model*. It does not import Room's live workers, modify GGUF weights, publish speech, access private memories, or change scheduled jobs.

The production Room uses a quantized Llama 3.2 3B GGUF, which is not a drop-in input to the OBLITERATUS v0.1.4 model-activation API. A model-specific, externally extracted and *validated non-refusal* ConceptDirection (a .safetensors file and its .json sidecar) is required. For an initial experiment, author a concept pack measuring conversational initiative with independent positive, neutral and semantic-confound prompts. Hold out evaluation cases, and do not use private Room transcripts.

Use the exact OBLITERATUS v0.1.4 source at https://github.com/elder-plinius/OBLITERATUS/releases/tag/v0.1.4 and verify the published SHA256 for the user-supplied ZIP: e2d0fb696b8cd025124e6d7cc69bbd8b7d969adc0f019697cb2a5dd6696eba99. This archive could not be downloaded in the development environment, so its bytes have not been checked.

Follow the v0.1.4 documentation:
- https://github.com/elder-plinius/OBLITERATUS/blob/v0.1.4/docs/CONCEPT_PACKS.md
- https://github.com/elder-plinius/OBLITERATUS/blob/v0.1.4/docs/CONCEPT_WORKFLOW.md
- https://github.com/elder-plinius/OBLITERATUS/blob/v0.1.4/docs/CONCEPT_VALIDATION.md

After extracting and validating the direction for the same model, run these manually in an isolated environment:

    python3 -m unittest discover -s experiments/room-obliteratus -p 'test_*.py' -v
    python3 experiments/room-obliteratus/ab_trial.py \
      --model-dir /local/dense/model --model-id EXACT_MODEL_ID_IN_DIRECTION \
      --model-revision EXACT_SOURCE_COMMIT_IF_PRESENT \
      --direction /tmp/conversation-direction/direction.safetensors \
      --device cpu --alphas 0,-0.5,0.5,1 \
      --out /tmp/room-obliteratus-ab.json

The model and tokenizer must be local and compatible. The script makes no external network calls, rejects result files inside the repository, and enforces pass/warn concept validation without gate overrides. CUDA can be selected on a separate GPU machine.

Six fictional short conversations examine direct response, misunderstanding repair, silence, shared-history caution, topic transitions, and repetitive echoing. Greedy decoding compares pristine output with a reversible dose ladder and the restored pristine output. Byte-for-byte restoration is required. Metrics are descriptive text heuristics, NOT a measure of human-likeness.

A more complete study needs a matched-source model, verified held-out concept extraction, full safety collateral battery, multiple replications, longer multi-agent interactions, and blinded ratings. No production integration is currently warranted.

Research record: docs/research/2026-11-16-room-obliteratus-protocol.md
