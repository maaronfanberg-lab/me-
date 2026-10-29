# Room causal-world cue: process-language leakage repair (2026-10-29)

## Observed failure
At cycle 36526, the 34 most recent public messages repeatedly speculated about whether an agent's public speech or body heat was causing the planetarium projector to dim. The displayed 120-turn experiment remained concrete in vocabulary but looped around a fabricated causal relationship to the agent system itself. The existing character-facing cue in `scripts/room_causal_world.py` literally said "an agent actually performs an action in public speech" and "publicly witnessed evidence." Those implementation terms can become apparent story facts, especially when the full recent transcript repeats them. We do not assert this is the only cause; the small model's abstraction preference and absence of physical follow-through also matter.

## Concrete mechanism
The source/provenance validator stays in code, while the speaking character receives only a concise in-world situation, their own observation, attributed real statements, physical outcomes, and whether the problem remains open. No internal labels such as *agent*, *public speech*, *source ID*, or *simulation* appear in the character-facing prompt. A scene clue is treated as communicated only when its owner actually made a firsthand public report; speculative questions or hypothetical theories no longer become a repeated source of shared physical evidence.

## Testing and limits
Regression cases include an exact paraphrase of the actual public-speech conjecture, a legitimate firsthand report from Jules, and a witnessed grille inspection. Test that no internal-control text is present in the rendered cue, prior actions still change the setting, the cue retains actual newline separators, and another character's private observation never leaks. Existing 120-turn bounds and visitor priority are unchanged.

This is a targeted contamination repair, not a proven cure for abstract language or weak initiative. Assess actual subsequent published speech and whether the group makes evidence-based progress without reintroducing a process-language attractor.
