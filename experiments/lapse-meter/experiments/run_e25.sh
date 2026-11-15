#!/bin/bash
# Run experiment 25's traces two at a time. Usage: bash experiments/run_e25.sh experiments/e25_jobs.txt results/e25.log
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$(dirname "$0")/.."
while IFS=$'\t' read -r cfg out; do [ -e "$out" ] && continue; printf '%s\0%s\0' "$cfg" "$out"; done < "$1" \
  | xargs -0 -n 2 -P 2 python3 -W ignore experiments/e25_trace.py >> "$2" 2>&1
echo ALLDONE >> "$2"
