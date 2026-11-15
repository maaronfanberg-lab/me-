"""Experiment 54: independent PyTorch (float32, autograd) re-implementation of the 96-layer one-matrix residual ReLU.
Shares nothing with lapse/ but the data (e4.make). Usage: python experiments/torch_replicate.py <task> <plain|cap10|norm> <seed>
Same architecture as lapse.nets.MLP(residual=True): h0 = relu(W0 x + b0); h_l = h_{l-1} + a relu(W_l h_{l-1} + b_l), a = 1/sqrt(96);
logits = W_out h_L + b_out; weights N(0, 1/fan_in), biases 0; SGD lr 0.05, batch 64, 6000 steps.
cap10: the readout's update scaled so its RMS logit change on the batch is at most 10. norm: readout lr x 64 / mean|h_L|^2.
Transport = ln(RMS dL/dh_1 / RMS dL/dh_L) on the first 256 training examples, read at loss 0.03 (0.1, 0.3 fallbacks)."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, torch
import e4
task, cond, seed = sys.argv[1], sys.argv[2], int(sys.argv[3])
torch.manual_seed(seed); g = torch.Generator().manual_seed(seed)
X, y, Xt, yt = e4.make(task, seed); X = torch.tensor(X, dtype=torch.float32); y = torch.tensor(y); Xt = torch.tensor(Xt, dtype=torch.float32); yt = torch.tensor(yt)
D, W, depth, K = X.shape[1], 64, 96, int(max(y.max(), yt.max()) + 1); a = depth ** -0.5
def lin(i, o): return [(torch.randn(o, i, generator=g) / i ** 0.5).requires_grad_(), torch.zeros(o, requires_grad=True)]
P = [lin(D, W)] + [lin(W, W) for _ in range(depth - 1)] + [lin(W, K)]
def fwd(x, keep=False):
    hs = []; h = torch.relu(x @ P[0][0].T + P[0][1])
    if keep: h.retain_grad(); hs.append(h)
    for Wl, bl in P[1:-1]:
        h = h + a * torch.relu(h @ Wl.T + bl)
        if keep: h.retain_grad(); hs.append(h)
    return h @ P[-1][0].T + P[-1][1], h, hs
ce = torch.nn.functional.cross_entropy; rng = np.random.default_rng(10_000 + seed); log = []
for s in range(6001):
    if s % 50 == 0:
        z, h, hs = fwd(X[:256], keep=True); l = ce(z, y[:256]); l.backward()
        rm = lambda t: float(torch.sqrt((t.grad ** 2).sum(1).mean()))
        with torch.no_grad(): tl = float(ce(fwd(X)[0], y))
        log.append(dict(step=s, train_loss=tl, transport=float(np.log(rm(hs[0]) / max(rm(hs[-1]), 1e-300)))))
        for p_ in P:
            for t in p_: t.grad = None
        if not np.isfinite(tl): break
    if s == 6000: break
    idx = torch.tensor(rng.integers(0, len(X), 64)); z, h, _ = fwd(X[idx]); ce(z, y[idx]).backward()
    with torch.no_grad():
        lr_out = 0.05
        if cond == "norm": lr_out *= 64.0 / max(float((h ** 2).sum(1).mean()), 1e-12)
        if cond == "cap10":
            dz = -lr_out * (h @ P[-1][0].grad.T + P[-1][1].grad); kb = float(torch.sqrt((dz ** 2).sum(1).mean()))
            if kb > 10: lr_out *= 10 / kb
        for i, (Wl, bl) in enumerate(P):
            lr = lr_out if i == len(P) - 1 else 0.05
            Wl -= lr * Wl.grad; bl -= lr * bl.grad; Wl.grad = None; bl.grad = None
with torch.no_grad(): acc = float((fwd(Xt)[0].argmax(1) == yt).float().mean())
out = os.path.join(HERE, "..", "results", "e54", f"{task}_{cond}_s{seed}.json"); os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(dict(task=task, cond=cond, seed=seed, test_acc=acc, log=log, torch=torch.__version__), open(out, "w")); print(out, log[-1], acc)
