#!/bin/bash
# Experiment 31: the twelve traced reruns, two at a time, skipping finished ones.
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$(dirname "$0")/.."
for t in digits circle-clean; do for k in relu signed; do for s in 0 1 2; do
  [ -e "results/e31/${t}_final_${k}_s${s}.json" ] || printf '%s\0%s\0%s\0' "$t" "$k" "$s"
done; done; done | xargs -0 -n 3 -P 2 python3 experiments/e31_trace.py >> results/e31.log 2>&1
echo ALLDONE >> results/e31.log
