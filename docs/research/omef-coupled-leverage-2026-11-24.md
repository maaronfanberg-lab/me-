# Coupled OMEF leverage experiments and inspection fixes — 2026-11-24

Reference: historical native solver recovered in branch commit e6efc761ceadba45cffd6c045d7618f2c28945fd. Compare individual link-strength min/max in mode 5 at global .45, mix .16, interference .16; both genomes at historical preset. Histograms normalized independently to their bounding boxes; TV is a geometry proxy, not visual proof.

1. At seed 1, 8,000 measured samples after 1,500 transient: average TV 0.4588 for native, 0.5110 for reference-anchored multiplier 1+2d², 0.5015 for k=5, 0.5088 for k=10. No individual reached .8.
2. Holdout seeds .5/.75/1.5/2, 5,000 measured samples after 1,000 transient: mean native TV .4328/.3997/.5310/.5205; k=2 .4763/.4544/.5334/.5697. No link reached .8; minimum dense mass ratio at some endpoints .76. Reject as universal fix.
3. Delayed source fluctuation augmentation, seed 1, 5,000 samples: mean TV .4041 native, .4159 k1, .4053 k2, .4292 k4. Inconsistent individual link response. Reject.
4. Native state blend from historical .16 setting toward B weight .65/.85/.95 at endpoint: all four tested seeds improved mix TV but none reached .8 and endpoint concentration reduced. Reject as automatic replacement pending visual evaluation.
5. Claude consultation bridge/outbox/omef-targeted-leverage-20261124-01.json: successful response, based on supplied facts rather than repo inspection. Phase cancellation, source saturation and response-metric ideas proposed; default-reference innovation gain has fragile baseline assumptions. Do not interpret proposed thresholds as measured outcomes.
6. Inspection fixes e5d52dde334f92d4dc43ae5e107e95086cf9a492: true drawing pause, historical reset restarts both engines and links, link circuit switches preserve unrelated controls, stable link slots distinguish identical routes, status reflects drawing vs evolution. 30,000 numerical steps compared to recovery reference (3 seeds), zero coordinate error; scripts parse. Browser smoke test added to branch and triggered, result not verified at writing.

No main app changes, no production deployment. Near-total independent link leverage not achieved. Further investigation should measure phase-dependent source/target response and clamp activity rather than assuming more force is sufficient. 
