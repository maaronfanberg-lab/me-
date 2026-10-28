"""probe_run.py with default settings must reproduce experiment 7 exactly (the instrumentation is additive).
Run: python tests/test_probe_run.py   (about 1 minute)"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "experiments")); sys.path.insert(0, ROOT)
from probe_run import run
ok_all = True
for task, act, depth in (("digits", "relu", 12), ("circle-clean", "tanh", 12)):
    ref = json.load(open(os.path.join(ROOT, "results", "e7", f"{task}_{act}_d{depth}_s0.json")))
    r = run(dict(task=task, act=act, depth=depth, seed=0))
    same = [a["Tstar"] for a in r["log"]] == [b["Tstar"] for b in ref["log"]] and \
           [a["train_loss"] for a in r["log"]] == [b["train_loss"] for b in ref["log"]] and r["test_acc"] == ref["test_acc"]
    ok_all &= same; print(("PASS " if same else "FAIL ") + f"{task} {act} d{depth}: probe_run log bit-identical to experiment 7")
print("2/2 reproduction checks passed" if ok_all else "reproduction FAILED"); sys.exit(0 if ok_all else 1)
