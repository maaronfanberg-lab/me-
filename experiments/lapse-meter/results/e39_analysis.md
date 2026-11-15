# Experiment 39 results

**Verdicts:** P39a (circle-embed64u does not diverge at ×10): holds; P39b (circle-pad62noise diverges at ×10): holds; P39c (frozen input layer prevents divergence): holds. Account supported: **scale**.

| condition | diverged at ×1 | at ×3 | at ×10 |
|---|---|---|---|
| circle-embed64u | 0 of 5 | 0 of 5 | 0 of 5 |
| circle-std1 | 0 of 5 | 0 of 5 | 5 of 5 |
| digits-pca2 | 0 of 5 | 3 of 5 | 5 of 5 |
| circle-pad62noise | 5 of 5 | 5 of 5 | 5 of 5 |
| digits_frozenin | 0 of 5 | 1 of 5 | 5 of 5 |
| circle-embed64_frozenin | 0 of 5 | 0 of 5 | 0 of 5 |
