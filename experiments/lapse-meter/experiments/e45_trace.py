"""Experiment 45 (exploratory): every-step trace of the blocks route (E40). Teardown blocked (block_nomean "all"),
input layer frozen, readout x10, digits, 300 steps; "slow" adds blocks at 0.1x. Uses e34_trace's hook.
Usage: python experiments/e45_trace.py <frozen|slow> <seed>"""
import os, sys, json, warnings
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from probe_run import run
from e34_trace import make_hook
warnings.filterwarnings("ignore")
cond, seed = sys.argv[1], int(sys.argv[2])
cfg = dict(task="digits", act="relu", depth=96, seed=seed, block_nomean="all", out_lr_mult=10, freeze=["in"], steps=300, log_every=1)
if cond == "slow": cfg["block_lr_mult"] = 0.1
lg = run(cfg, hook=make_hook())["log"]
keep = [{k: v for k, v in e.items() if k not in ("stream_grad", "gate", "stream_norm", "branch_ratio", "density", "dead", "sg_by_block", "open_by_block")} for e in lg]
out = os.path.join(HERE, "..", "results", "e41_46", f"E45_{cond}_s{seed}.json"); os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(dict(config=cfg, log=keep), open(out, "w")); print(out, "last step", lg[-1]["step"], flush=True)
