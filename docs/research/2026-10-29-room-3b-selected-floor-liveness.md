# Room 3B speech-first liveness, 2026-10-29

## Observation and baseline
The public Room state was fixed at cycle 34976 (last accepted speech 2026-10-29 01:51 UTC). A cancelled Room Actions job (run 40859013943, job 123397175032) started 10:37 UTC and reported four comprehension Timeouts, repeated thought Timeouts, zero published beats, then cancellation. The same signature appeared in 40858415752. The server successfully identified `ROOM_BRAIN_ACTIVE=llama3.2-3b`, but `scripts/room_engine_v5.py` registered the selected-floor speech-first adapter **only** for `llama3.2-1b`. Consequently the 3B deployment used older structured calls and saturated a two-slot CPU server instead of the intended one-turn speech adapter.

## Research question
Can the selected-floor production path be restored without synthetic speech or untested changes to content policy by fixing backend routing and avoiding unnecessary model calls?

## 10-level research gate
1. Problem: confirmed stack traces from current cancelled production jobs; state not advancing.
2. Foundational: Sacks, Schegloff & Jefferson (1974), *A simplest systematics for the organization of turn-taking for conversation*, Language 50:696-735. One conversational turn should not require nine competing generative submissions.
3. Current documentation: llama.cpp upstream server README (https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md), especially `-np` parallel slots, and the server developer README describing the shared inference bottleneck and HTTP request queue (https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README-dev.md). Checked 2026-10-29.
4. Natural behavior: conversation turn-taking is one speaker's contribution followed by uptake, not forced model output from every observer; adaptation from human data remains limited.
5. Mechanism: the intended native chat backend already plans one public utterance in a single pass. The selector explicitly supports no separate deliberated bid, and the eight node schema is maintained.
6. Alternatives: hosted model unavailability, stale public cache, and Git push races cannot explain repeated localhost inference timeouts before the commit phase; a better server could still help.
7. Limitations: the patch does not prove conversation quality or guarantee adequate inference speed. Native 3B speech can still time out, be quarantined, or fail final preflight.
8. Transfer: human turn-taking describes interactional sequencing, not model speed. The CPU throughput claim follows the observed server logs and published server implementation, not social psychology.
9. Mapping: register the speech adapter for both verified Llama 1B and Llama 3B labels. In selected-floor + native-chat mode, omit comprehension/thought LLM generations that are unused by the single-pass chat prompt, but retain all eight cognitive node records, selector, preflight and commit safety checks. Do not change legacy mode.
10. Validation: import-time 3B binding regression test; speech adapter and all floor integration tests; branch CI; after merge confirm a public cycle advance, `diagnostic_only=false`, `speech_backend=native_chat_v1`, and actual responsive utterances. Roll back if semantic integrity fails.

## Pre-change outcome
No public cycles after 34976 and repeated comprehension/thought timeouts followed by supervisor replacement. Production 3B failed to select the actual native speech adapter.

## Post-change outcome
Pending independent workflow and live-feed verification. A passing unit test alone is not a claim of production success.
