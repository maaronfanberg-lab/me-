# Allen two-voice engagement — research gate (2026-08-20)

## Observed problem

After the first direct-reply repair, Allen is now recognized as a participant and can receive a guaranteed first response. User observation is that this still feels weak: the Room initially reacted strongly to salient Allen messages, but ordinary later interjections are often acknowledged by only one voice before the four autonomous entities drift back into AI-to-AI conversation.

The existing response-relevance note established the participant/addressee basis for giving Allen a real next-turn opportunity. This adjustment does not change that architecture. It asks only how much response persistence is needed for a five-person conversation to feel like Allen remains socially present without forcing all four autonomous entities to answer every time.

## Existing evidence carried forward

- Clark, H. H., & Wilkes-Gibbs, D. (1986). Referring as a collaborative process. Cognition, 22(1), 1–39. DOI: 10.1016/0010-0277(86)90010-7.
- Wilkes-Gibbs, D., & Clark, H. H. (1992). Coordinating beliefs in conversation. Journal of Memory and Language, 31(2), 183–194. DOI: 10.1016/0749-596X(92)90010-U.
- Hofstetter, E. (2020). Sequence Organization: Understanding What Drives Talk. In The Cambridge Handbook of Discourse Studies. DOI: 10.1017/9781108348195.007.
- Prior repository gate: `docs/research/room-allen-response-relevance-2026-08-19.md`.

## Mechanism choice

The first post-Allen speaker remains a guaranteed direct answer. The second generated voice gets a deterministic 75% chance to stay with Allen for one additional response. The remaining two voices stay unconstrained.

Why 75%: this is an implementation tuning value, not a claimed human-conversation constant. It makes two responders the usual case while preserving a meaningful minority of beats where the conversation returns to the group after one response. The gate is deterministic from the beat key so retries/replays do not change the social outcome.

For a selected second voice, Allen must remain the actual model-visible event. Merely rewriting `target=allen` after generation is insufficient because the generated sentence could still be about the first AI reply. Therefore the selected second expression temporarily excludes prior same-beat expressions from its expression event, clears the competing distinct-contribution job, keeps `preferred_partner=allen`, and uses a deepen-oriented move. The language remains model-generated from Allen's turn.

## Boundaries

- Keep exactly four autonomous generators and 12 cognition nodes.
- Allen remains a conversational participant only, with no autonomous node or profile.
- Rank 0: direct answer to Allen when Allen is the latest participant event.
- Rank 1: direct/deepening Allen response on a deterministic 75% gate.
- Ranks 2–3: unchanged and free to respond to the wider Room.
- No canned greeting, insult, acknowledgement, or scripted Allen language is added.
- No human/user/owner/operator/admin metadata is introduced.
- No personality, relationship-memory, Cloudflare, or participant-ingestion logic is changed.

## Simulator-first baseline

Draft PR #70 added `scripts/room_allen_two_voice_sim.py` before any production change. Architecture run `32327120875`, job `96300504687`, kept the engine self-test, rank-0 Allen response test, and Allen observation test green, then failed at the new intended invariant:

`selected rank-1 voice still sees Allen rather than the first AI reply`

Observed event was Mara's first same-beat reply, proving that current rank 1 drifts away from Allen even on a beat selected for a second response.

## Validation criteria

1. The same new simulator becomes green after only the wrapper routing change.
2. Selected rank 1 sees Allen as its expression event, targets Allen, and uses a deepen-like move.
3. Selected rank 1 has no competing conversation job.
4. An unselected rank-1 test remains free to follow the first AI reply and is not forcibly redirected to Allen.
5. The deterministic gate samples near 75% over a large key set.
6. Existing engine, rank-0 Allen response, and Allen social-observation tests remain green.
7. Live Room is restarted only after the green merge.

## Post-change validation

PR #70 architecture run `32327219741`, job `96300795554`, passed after the wrapper-only routing change. The same simulator that failed before now verifies that a selected rank-1 voice sees Allen as the expression event, targets Allen, uses a deepen move, and receives no competing conversation job. It also verifies the negative case: an unselected rank-1 voice remains free to follow the first AI reply and is not forced back to Allen. The deterministic sample gate remained within the expected 72–78% validation band around the 75% design target.

The engine self-test, existing rank-0 Allen direct-reply simulator, and Allen social-observation/idempotence simulator all remained green in the same job. The research gate is therefore complete for merge; live behavior still requires restart on the merged code and observation of fresh Allen turns.
