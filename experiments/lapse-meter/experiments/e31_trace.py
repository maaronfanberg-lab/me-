"""Experiment 31 (exploratory): where does final-LayerNorm ReLU's extra transport come from?

Experiment 26 found that 96-layer residual ReLU with a final LayerNorm ends with more transport than its signed twin
(digits +0.75 against +0.54 at loss 0.03; circle +1.11 against +0.60). This reruns those exact runs (probe_run.py,
same configs) with a logging hook that splits every example's stream gradient g_i at the top (the readout's side,
layer L-1) and at the bottom (block 1) into the batch-mean part gbar (the same request to every example's stream) and
the example-specific rest g_i - gbar:
  share_top, share_bot      |gbar|^2 / mean_i |g_i|^2 at each end (1 = every example gets the same gradient)
  tr_specific               ln( rms(g_1 - gbar_1) / rms(g_L - gbar_L) ): transport of the example-specific part only
  tr_shared                 ln( |gbar_1| / |gbar_L| ): transport of the shared part only
  mshare_bot                share of the bottom gradients' energy along the bottom stream's mean direction m_1
The hook does not touch the weights or the random generator, so each run's log must equal experiment 26's exactly;
the script checks that before writing.
Usage: python experiments/e31_trace.py <task> <relu|signed> <seed>
"""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, ".."))
import numpy as np
from probe_run import run

rms = lambda a: float(np.sqrt(np.mean(np.sum(a * a, 1))))


def hook(net, X, y):
    _, _, _, _, g = net.backward(X, y)
    h, _ = net.forward(X)
    L = len(net.W); gt, gbo = g[L - 2], g[1]
    mt, mb = gt.mean(0), gbo.mean(0)
    share = lambda G, m: float(np.sum(m * m) / np.mean(np.sum(G * G, 1)))
    u = h[2].mean(0); u = u / np.linalg.norm(u)  # mean direction of the stream after block 1 (h[2]), as g[1] sees it
    return dict(share_top=share(gt, mt), share_bot=share(gbo, mb),
                tr_specific=float(np.log(rms(gbo - mb) / rms(gt - mt))),
                tr_shared=float(np.log(np.linalg.norm(mb) / np.linalg.norm(mt))),
                mshare_bot=float(np.mean((gbo @ u) ** 2) / np.mean(np.sum(gbo * gbo, 1))))


if __name__ == "__main__":
    task, kind, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
    ref_path = os.path.join(HERE, "..", "results", "e26", f"{task}_final_{kind}_s{seed}.json")
    ref = json.load(open(ref_path)); cfg = ref["config"]
    r = run(cfg, hook=hook)
    same = [e["train_loss"] for e in r["log"]] == [e["train_loss"] for e in ref["log"]] and \
           [e["ln_transport"] for e in r["log"]] == [e["ln_transport"] for e in ref["log"]]
    assert same, "trace does not reproduce experiment 26"
    out = os.path.join(HERE, "..", "results", "e31", f"{task}_final_{kind}_s{seed}.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(dict(config=cfg, reproduces_e26=same, log=r["log"]), open(out, "w"))
    print(out, "reproduces experiment 26:", same, flush=True)
