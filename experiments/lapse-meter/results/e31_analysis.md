# Experiment 31 results (exploratory)

Read at the first logged step with training loss below 0.03; means ± sd over 3 seeds.

| task | network | step | transport | example-specific transport | shared transport | shared share, top | shared share, bottom | bottom energy along m |
|---|---|---|---|---|---|---|---|---|
| digits | relu | 650 | +0.75 ± 0.09 | +0.75 ± 0.09 | +0.77 ± 0.08 | +0.01 ± 0.01 | +0.01 ± 0.01 | +0.00 ± 0.00 |
| digits | signed | 567 | +0.53 ± 0.02 | +0.53 ± 0.02 | +0.47 ± 0.15 | +0.00 ± 0.00 | +0.00 ± 0.00 | +0.00 ± 0.00 |
| circle-clean | relu | 200 | +1.16 ± 0.10 | +1.16 ± 0.11 | +1.03 ± 0.09 | +0.02 ± 0.01 | +0.02 ± 0.01 | +0.12 ± 0.04 |
| circle-clean | signed | 100 | +0.61 ± 0.08 | +0.61 ± 0.08 | +0.45 ± 0.08 | +0.01 ± 0.01 | +0.00 ± 0.00 | +0.01 ± 0.02 |

- digits: total gap +0.22, example-specific gap +0.22 (ratio 1.00)
- circle-clean: total gap +0.55, example-specific gap +0.55 (ratio 1.00)

**Answer (signature in E31_PLAN.md): mixed.**
