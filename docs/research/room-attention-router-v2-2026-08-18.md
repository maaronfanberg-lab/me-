# Room attention router v2 — research record

Date: 2026-08-18

## Observed problem

The first live v1 telemetry showed a concrete over-routing failure: Sarah's thought node selected both `emotional-attunement` and `social-grounding` from the single shared trigger `trust`. The mechanism worked, but weak ambiguous evidence could spend the full two-skill budget on overlapping procedures.

## Research question

Can the selective-context architecture be made more conservative without losing strong specialist routing, while implementing the paper's resident/project/reference distinction more faithfully?

## Evidence and limitations

The evidence base from the v1 research record still applies: irrelevant context can distract language models, while relevant context can help. The 2026 `@skills` paper supports separating permanent residency, project-local capabilities, and explicit reference capabilities, but it does not establish an optimal automatic router for this Room. Therefore v2 changes only the routing mechanism and preserves the existing cognition engine and private role prompts.

The new live evidence is local rather than general: one weak lexical cue caused two skills to load. That observation justifies reducing ambiguous trigger sensitivity, not replacing deterministic routing with an unvalidated learned router.

## Mechanism change

1. Keep the private role prompt as the resident core.
2. Keep `skills/room/` as project skills eligible for implicit relevance routing.
3. Add `skills/reference/` as an explicit-only tier. Reference skills never auto-route from conversation text; callers must name them through `ROOM_REFERENCE_SKILLS`.
4. Weight recent public utterances more strongly than older conversation and topic residue.
5. Give comprehension and expression a one-skill budget; thought may use two skills.
6. Use role-specific character budgets instead of one global 1,200-character ceiling.
7. Give multi-word trigger evidence more weight than a single lexical cue.
8. Prevent weak candidates supported by exactly the same evidence from stacking.
9. Apply a small repeat penalty only when the same node selected the same skill on the previous beat and current evidence is weak; strong repeated evidence is not penalized.
10. Publish score, confidence, tier, domain, evidence-source type, repeat penalty, and budget metadata without logging conversation text or private prompts.

## Competing explanations and transfer limits

- Repeated use of the same specialist can be correct when a conversation genuinely remains in one domain, so the repeat penalty is deliberately small and disabled for strong evidence.
- Lexical triggers still cannot capture all semantic relevance. V2 improves evidence weighting and ambiguity handling but is not a semantic embedding router.
- Lower budgets may create false negatives. The no-match path remains the original resident prompt, so a routing miss does not remove baseline cognition.
- Reference-tier support is architectural capability, not evidence that the Room should automatically invoke large specialist procedures.

## Validation criteria

- Existing Room architecture smoke test remains green.
- Router regression suite expands from 5 to 11 tests.
- Strong technical context continues to route `technical-systems`.
- Explicit emotional context continues to route `emotional-attunement`.
- `trust` alone does not summon two overlapping specialists.
- Comprehension and expression load at most one temporary skill; thought loads at most two.
- Each role stays within its own temporary-character budget.
- Reference skills never auto-route and can be loaded only by explicit request.
- Weak repeated matches can be suppressed; strong repeated evidence still routes.
- Audit files contain fingerprints and routing metadata but no raw conversation or prompt content.

## Revert criteria

Revert v2 if live beats begin failing because of the router, cadence degrades materially, strong relevant specialists disappear systematically, reference skills load without explicit requests, private text appears in telemetry, or output quality visibly worsens and recovers when v2 is disabled.

## Post-change status

PR #63 merged to `main` on 2026-08-18. GitHub's Room Attention Smoke job compiled the router and ran all 11 regression tests successfully. The Room restart was issued immediately after merge. At the final verification point, the repository still contained the last v1 attention record from 15:16:44 UTC and no post-restart v2 beat had been committed yet, so live v2 telemetry remained the only pending deployment observation.
