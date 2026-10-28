"""Measure the four experiment-22 predictors at initialization for every SGD run of experiments 8-19, alongside
that run's outcome. Writes results/e22_predictors.json (one record per run)."""
import sys, os, json, glob, warnings
warnings.filterwarnings("ignore")
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np
from e22_predictors import predictors
from e8_analyze import at_loss_key, R
out_path = os.path.join(R, "e22_predictors.json")
done = json.load(open(out_path)) if os.path.exists(out_path) else {}
files = sorted(f for e in ("e8", "e9", "e10", "e11", "e12", "e13", "e14", "e15", "e16", "e17", "e19") for f in glob.glob(os.path.join(R, e, "*.json")))
for i, f in enumerate(files):
    key = os.path.relpath(f, R)
    if key in done: continue
    r = json.load(open(f)); c = r["config"]
    if c.get("opt", "sgd") != "sgd": continue
    p = predictors(c)
    task = c["task"]; t = at_loss_key(r["log"], 0.03, "ln_transport")
    failed = r["log"][-1]["train_loss"] > 0.5 * np.log(10 if task == "digits" else 2)
    done[key] = dict(config=c, transport=None if t is None or not np.isfinite(t) else float(t), failed=bool(failed),
                     final_loss=r["log"][-1]["train_loss"], test_acc=r["test_acc"], **p)
    json.dump(done, open(out_path, "w"))
    print(f"{i + 1}/{len(files)} {key}: kick {p['kick']:.3g} sharp {p['sharp']:.3g} corr {p['corr']:.2f} blockstep {p['blockstep']:.3g} -> transport {t}", flush=True)
print("MEASURED", len(done))
