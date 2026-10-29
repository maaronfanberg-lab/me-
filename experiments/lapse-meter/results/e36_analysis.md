# Experiment 36 results

**Verdicts:** P36a (nomean prevents the teardown, both tasks): holds; P36b (nomean diverges on digits): holds; P36c (nomean + cap 10 healthy, both tasks): holds.

**Decision (digits):** the teardown is the escape.

| task | condition | seed | stream step 5 / step 0 | transport | last step | final loss | state |
|---|---|---|---|---|---|---|---|
| digits | nomeanall | 0 | 76.988 | – | 0 | 57.77 | **diverged** |
| digits | nomeanall | 1 | 2.335 | – | 0 | 54.58 | **diverged** |
| digits | nomeanall | 2 | 6.014 | – | 0 | 41.38 | **diverged** |
| digits | nomeanall | 3 | 5.171 | – | 0 | 44.19 | **diverged** |
| digits | nomeanall | 4 | 4.965 | – | 0 | 24.11 | **diverged** |
| digits | nomeanall_cap10 | 0 | 0.713 | +1.59 | 6000 | 0.0002771 | **healthy** |
| digits | nomeanall_cap10 | 1 | 0.689 | +1.59 | 6000 | 0.0002852 | **healthy** |
| digits | nomeanall_cap10 | 2 | 0.776 | +1.69 | 6000 | 0.0002748 | **healthy** |
| digits | nomeanall_cap10 | 3 | 0.743 | +1.60 | 6000 | 0.000266 | **healthy** |
| digits | nomeanall_cap10 | 4 | 0.857 | +1.55 | 6000 | 0.0002427 | **healthy** |
| circle-clean | nomeanall | 0 | 0.821 | +3.02 | 6000 | 0.02009 | **healthy** |
| circle-clean | nomeanall | 1 | 0.901 | +2.70 | 6000 | 0.02032 | **healthy** |
| circle-clean | nomeanall | 2 | 0.810 | +3.00 | 6000 | 0.02067 | **healthy** |
| circle-clean | nomeanall | 3 | 0.837 | +2.93 | 6000 | 0.01904 | **healthy** |
| circle-clean | nomeanall | 4 | 0.812 | +2.87 | 6000 | 0.02053 | **healthy** |
| circle-clean | nomeanall_cap10 | 0 | 0.987 | +2.98 | 6000 | 0.02103 | **healthy** |
| circle-clean | nomeanall_cap10 | 1 | 0.995 | +2.61 | 6000 | 0.02106 | **healthy** |
| circle-clean | nomeanall_cap10 | 2 | 0.976 | +3.03 | 6000 | 0.02158 | **healthy** |
| circle-clean | nomeanall_cap10 | 3 | 0.990 | +2.85 | 6000 | 0.02017 | **healthy** |
| circle-clean | nomeanall_cap10 | 4 | 0.979 | +2.93 | 6000 | 0.02153 | **healthy** |
