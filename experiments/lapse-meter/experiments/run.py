"""One training run, logging depth geometry and per-layer weight motion. Usage:
    python experiments/run.py '<json config>' out.json
Config keys: task (digits|circle), depth, width, act, sigma_w, residual, opt (sgd|adam), lr, steps, batch, seed,
log_at (list of steps), clock_window (steps over which per-layer weight motion is averaged, from step 0).
"""
import sys, os, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from lapse import geometry
from lapse.nets import MLP, SGD, Adam
from lapse import data as D


def run(cfg):
    task = cfg.get("task", "digits")
    X, y, Xt, yt = (D.digits if task == "digits" else D.circle)(cfg["seed"])
    nclass = int(max(y.max(), yt.max()) + 1)
    net = MLP(X.shape[1], cfg.get("width", 64), cfg["depth"], nclass, act=cfg["act"], sigma_w=cfg["sigma_w"],
              residual=cfg.get("residual", False), seed=cfg["seed"])
    opt = SGD(cfg["lr"]) if cfg.get("opt", "sgd") == "sgd" else Adam(cfg["lr"])
    rng = np.random.default_rng(10_000 + cfg["seed"])
    probe = (X[:256], y[:256])
    log_at = set(cfg.get("log_at", [0, 100, 300, 1000, 3000]))
    win = cfg.get("clock_window", 0)
    motion = np.zeros(len(net.W)); lapse_acc = None; nwin = 0
    out = {"cfg": cfg, "log": []}
    for s in range(cfg["steps"] + 1):
        if s in log_at:
            _, _, _, d = net.backward(*probe)
            g = geometry(net.geometry_deltas(d))
            fin = bool(np.all(np.isfinite(g.lapse)))
            out["log"].append(dict(step=s, lapse=[float(v) for v in g.lapse], tilt=g.tilt if fin else None,
                                   kappa=g.kappa if fin else None, test_acc=net.accuracy(Xt, yt),
                                   train_acc=net.accuracy(X, y), loss=net.loss(X, y)))
        if s == cfg["steps"]:
            break
        idx = rng.integers(0, len(X), cfg.get("batch", 64))
        _, gW, gb, d = net.backward(X[idx], y[idx])
        if not all(np.all(np.isfinite(w)) for w in gW):
            out["diverged_at"] = s; break
        if s < win:
            before = [w.copy() for w in net.W]
        opt.step(net, gW, gb)
        if s < win:
            motion += np.array([np.linalg.norm(w - w0) / (np.linalg.norm(w0) + 1e-30) for w, w0 in zip(net.W, before)])
            pd = net.backward(*probe)[3]
            from lapse.core import lapse_profile
            Np = lapse_profile(pd)  # all layers incl. layer 0, normalised to output
            lapse_acc = Np if lapse_acc is None else lapse_acc + Np
            nwin += 1
    if win and nwin:
        out["clock"] = dict(motion=(motion / nwin).tolist(), lapse=(lapse_acc / nwin).tolist())
    return out


if __name__ == "__main__":
    cfg = json.loads(sys.argv[1]); t0 = time.time()
    res = run(cfg); res["seconds"] = time.time() - t0
    json.dump(res, open(sys.argv[2], "w"))
    last = res["log"][-1]
    print(os.path.basename(sys.argv[2]), f"tilt {res['log'][0]['tilt']} -> {last['tilt']}  test {last['test_acc']:.3f}  {res['seconds']:.0f}s", flush=True)
