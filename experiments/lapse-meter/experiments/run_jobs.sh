#!/bin/bash
# Run a job file (lines: <json config><TAB><output path>) two at a time, skipping outputs that already exist.
# Usage: bash experiments/run_jobs.sh experiments/e8_jobs.txt results/e8.log
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$(dirname "$0")/.."
while IFS=$'\t' read -r cfg out; do
  [ -e "$out" ] && continue
  printf '%s\0%s\0' "$cfg" "$out"
done < "$1" | xargs -0 -n 2 -P 2 python3 experiments/probe_run.py >> "$2" 2>&1
echo ALLDONE >> "$2"
