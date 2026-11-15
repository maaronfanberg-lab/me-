# Society brain

The society is designed so its conversational model is stored by GitHub with this repository rather than supplied by an external inference API.

## Brain asset

- Release tag: `society-brain-v1`
- Asset: `society-brain-q4_0.gguf`
- Model: Qwen2.5-0.5B-Instruct GGUF q4_0
- Parameters: approximately 0.49B
- License: Apache-2.0
- SHA256: `7671c0c304e6ce5a7fc577bcb12aba01e2c155cc2efd29b2213c95b18edaf6ed`

The one-time bootstrap workflow copied the model into a Release belonging to `maaronfanberg-lab/me-`. Normal society turns load the model from that Release only.

## Runtime

The same Release stores the Linux x64 CPU runtime:

- Asset: `llama-runtime-linux-x64.tar.gz`
- Runtime: llama.cpp Ubuntu x64 release `b10441`
- Release target commit: `0177dcc7300bad8914bb838baabce87899812491`
- SHA256: `360a5bfab5b8fe562c52e060a998a052f5fc7d98a0448b035c2eedbb6acfbd94`

Normal society turns load this runtime from the same GitHub Release. There is no Copilot, GitHub Models, or external inference API fallback in the society node code.

## Permanent state

The entity genomes, learned development, retained memories, shared transcript, and room state are stored under `society/` and committed back to GitHub after successful turns.

GitHub-hosted Actions runners are temporary execution environments. They may hold a working copy of the model in memory/disk while a node is thinking, but the persistent model, runtime, minds, memories, and conversation state remain stored by GitHub.
