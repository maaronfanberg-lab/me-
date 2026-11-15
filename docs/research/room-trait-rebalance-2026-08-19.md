# Room trait rebalance — 2026-08-19

## Observed problem

The current four personalities are too uniformly cooperative for the desired Room dynamic. The requested change is narrower than adding insult scripts or new orchestration: bias some entities toward greater assertiveness/antagonism, while making Mara more conflict-sensitive and more likely to express hurt feelings.

## Research question

Can the desired change be produced by adjusting only the existing personality trait values, without adding new prompt rules, canned insults, targeting rules, or new social-state machinery?

## Evidence

Foundational and current evidence checked 2026-08-19:

- Graziano, Jensen-Campbell & Hair (1996), JPSP, doi:10.1037/0022-3514.70.4.820 — lower Agreeableness is associated with different conflict tactics, including greater relative endorsement of power assertion.
- Jensen-Campbell & Graziano (2001), Journal of Personality, doi:10.1111/1467-6494.00148 — Agreeableness is closely associated with affective and tactical responses during interpersonal conflict.
- Hyatt et al. (2020), Aggressive Behavior, doi:10.1002/ab.21887 — lower Agreeableness/antagonism facets are among the more consistent personality correlates of laboratory aggression, with effects that are meaningful but not deterministic.
- Kim et al. (2013), Psychiatry Investigation / PMC3569159 — higher neuroticism/emotional sensitivity is associated with stronger negative emotional responses to interpersonal stress; the transfer here is to the repository's existing `emotional_reactivity` and `social_sensitivity` dimensions, not to a clinical construct.
- Hudson & Rufino (2025), Personality Disorders: Theory, Research, and Treatment, doi:10.1037/per0000723 — antagonism remains a useful contemporary personality construct, but it should not be treated as a guarantee of any specific hostile act.

## Limitations

- “Victim-like” is not a clean Big Five trait. In this implementation it is translated into higher emotional reactivity, higher social sensitivity, higher self-disclosure, and somewhat greater inhibition/agreeableness, so Mara is more likely to register and verbalize interpersonal hurt rather than being scripted as helpless.
- Trait values bias model behavior but cannot guarantee insults, attacks, hurt feelings, or any particular utterance.
- The current model-input orchestration leak is a separate problem. This change must not add or rename model-visible control instructions.

## 10-level gate

1. Observed problem — PASS: current traits and recent Room behavior are directly observed.
2. Foundational evidence — PASS: Big Five Agreeableness/conflict findings support the direction of change.
3. Current evidence — PASS WITH LIMITS: newer aggression/antagonism literature supports lower Agreeableness as a conflict/aggression correlate, not a deterministic behavior switch.
4. Natural-behavior evidence — PASS: diary/laboratory interpersonal-conflict studies inform the mapping.
5. Mechanism evidence — PASS: use existing dispositional trait inputs only.
6. Competing explanations — PASS: scripted insults would produce stronger immediate effects but would be brittle and easier for entities to detect as machinery.
7. Replication/correction/limitations — PASS WITH LIMITS: effects are probabilistic and generally modest.
8. Context transfer — PASS WITH CAUTION: human personality findings are used only as directional priors for a simulated four-entity system.
9. Implementation mapping — PASS: edit only `room/config.json` trait values; no prompt, workflow, social algorithm, or memory changes.
10. Post-change validation — DEFINED: JSON must remain valid, all traits remain in [0,1], Sarah/Owen/Jules must shift toward lower Agreeableness and/or lower inhibition/higher skepticism, and Mara must shift toward higher emotional reactivity/social sensitivity/self-disclosure. Observe live conversation before adding any further conflict mechanism.

## Proposed trait direction

- Sarah: more assertive and skeptical; lower agreeableness and inhibition, moderately higher extraversion.
- Owen: strongest adversarial bias; much lower agreeableness, very high skepticism, lower inhibition, somewhat higher extraversion.
- Jules: bolder teasing style; lower agreeableness/inhibition, higher extraversion, skepticism and humor.
- Mara: more conflict-sensitive and emotionally expressive; higher emotional reactivity, social sensitivity and self-disclosure, slightly higher inhibition and agreeableness, lower skepticism.
