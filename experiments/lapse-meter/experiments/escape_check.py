"""Checks of THEORY_KICK.md amendment 3 (the "escape" account), predictions E-i and E-ii, fixed before these runs.

Plain 96-layer residual ReLU, width 64, SGD, seed 0, both tasks, 500 steps, at lr 0.02, 0.05 and 0.1 (probe_run.py,
with a read-only hook every 10 steps). The hook measures, on the 256-example probe batch:
  stream     RMS of the last stream h_L (the readout's input)
  eta_lout   lr * the largest eigenvalue of the exact Hessian of the probe-batch loss over the readout's weights and
             bias alone: H = (1/n) sum_i (diag(p_i) - p_i p_i^T) kron x_i x_i^T with x_i = [h_i, 1].
             Built explicitly (K*(w+1) square, at most 650) and diagonalized, so nothing is approximated.
             tests/test_escape_check.py checks it against finite differences of the readout gradient.
E-i:  stream RMS at step 500, lr 0.02 / lr 0.1, within 1.7-2.9 on each task (sqrt 5 = 2.24 predicted).
E-ii: eta_lout between 1 and 4 at steps 100-500 at lr 0.05, both tasks (median over those steps; range reported).
Writes results/escape_check.json and results/escape_check.md.
"""
import os, sys, json, warnings
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, ".."))
import numpy as np
from probe_run import run
from e8_analyze import R
warnings.filterwarnings("ignore")


def readout_hessian(net, X):
    h = net.forward(X)[0]; x = h[-2]; z = h[-1]
    p = np.exp(z - z.max(1, keepdims=True)); p /= p.sum(1, keepdims=True)
    xa = np.hstack([x, np.ones((len(x), 1))]); n, K = p.shape; d = xa.shape[1]
    H = np.zeros((K * d, K * d))
    for i in range(n):
        A = np.diag(p[i]) - np.outer(p[i], p[i])
        H += np.kron(A, np.outer(xa[i], xa[i]))
    return H / n  # ordering: class-major, matching W_out[k, :] with the bias as the last column


def make_hook(lr):
    def hook(net, X, y):
        lam = float(np.linalg.eigvalsh(readout_hessian(net, X))[-1])
        return dict(stream=float(np.sqrt(np.mean(np.sum(net.forward(X)[0][-2] ** 2, 1)))), eta_lout=lr * lam)
    return hook


if __name__ == "__main__":
    out = {}
    for task in ("digits", "circle-clean"):
        for lr in (0.02, 0.05, 0.1):
            r = run(dict(task=task, act="relu", depth=96, seed=0, lr=lr, steps=500, log_every=10), hook=make_hook(lr))
            out[f"{task}_lr{lr}"] = [dict(step=e["step"], loss=e["train_loss"], transport=e["ln_transport"], stream=e["stream"], eta_lout=e["eta_lout"]) for e in r["log"]]
            print(task, lr, "done", flush=True)
    os.makedirs(R, exist_ok=True); json.dump(out, open(os.path.join(R, "escape_check.json"), "w"))
    md = ["# Escape account checks (THEORY_KICK.md amendment 3)\n", "| task | lr | stream at 0 → 500 | η·λ_out at step 0 | η·λ_out steps 100–500, median [range] | transport at 500 | loss at 500 |", "|---|---|---|---|---|---|---|"]
    V = {}
    for task in ("digits", "circle-clean"):
        for lr in (0.02, 0.05, 0.1):
            L = out[f"{task}_lr{lr}"]; late = [e["eta_lout"] for e in L if 100 <= e["step"] <= 500]
            md.append(f"| {task} | {lr} | {L[0]['stream']:.0f} → {L[-1]['stream']:.1f} | {L[0]['eta_lout']:.3g} | {np.median(late):.2f} [{min(late):.2f}–{max(late):.2f}] | {L[-1]['transport']:+.2f} | {L[-1]['loss']:.3f} |")
        ratio = out[f"{task}_lr0.02"][-1]["stream"] / out[f"{task}_lr0.1"][-1]["stream"]
        late = [e["eta_lout"] for e in out[f"{task}_lr0.05"] if 100 <= e["step"] <= 500]
        V[task] = (ratio, 1.7 <= ratio <= 2.9, float(np.median(late)), 1 <= np.median(late) <= 4)
    md.append("")
    for task, (ratio, ok1, med, ok2) in V.items():
        md.append(f"- {task}: E-i stream ratio lr 0.02 / 0.1 = {ratio:.2f} → **{'holds' if ok1 else 'fails'}**; E-ii median η·λ_out at lr 0.05 = {med:.2f} → **{'holds' if ok2 else 'fails'}**")
    t = "\n".join(md); print(t); open(os.path.join(R, "escape_check.md"), "w").write(t + "\n")
