"""Experiment 55: a small transformer on the pinned character corpus (PyTorch). Usage: <depth> <plain|cap10|norm|finalln> <seed>
Pre-residual blocks without normalization: h += a*Attn(h); h += a*MLP(h), a = 1/sqrt(2*depth); d=64, 4 heads, MLP 4x, ReLU,
causal, context 16; learned token + position embeddings (std 1). Readout on the last position (next character).
finalln: LayerNorm (no affine) before the readout. cap10 / norm: as experiment 54, on the readout. SGD lr 0.05, batch 64, 6000 steps.
Transport = ln(RMS dL/dh after block 1 / RMS dL/dh after the last block), at the last position, on 256 training windows."""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import numpy as np, torch, torch.nn as nn
import tiny_lm as T
depth, cond, seed = int(sys.argv[1]), sys.argv[2], int(sys.argv[3]); torch.manual_seed(seed)
onemat = cond.startswith("one")  # one-matrix ReLU branch h += a*relu(W h) in place of the two-matrix MLP (pile-up test)
base = cond.split("_", 1)[1] if onemat and "_" in cond else ("plain" if onemat else cond)
txt, chars = T.corpus(); ids = torch.tensor(T.encode(txt, chars)); V, C, d = len(chars), 16, 64
r0 = np.random.default_rng(0); starts = r0.choice(len(ids) - C - 1, 9000, replace=False)
Xall = torch.stack([ids[s:s + C] for s in starts]); Yall = torch.stack([ids[s + C] for s in starts])
X, Y, Xt, Yt = Xall[:8000], Yall[:8000], Xall[8000:], Yall[8000:]
a = (2 * depth) ** -0.5
class Block(nn.Module):
    def __init__(s):
        super().__init__(); s.q, s.k, s.v, s.o = (nn.Linear(d, d) for _ in range(4)); s.f1, s.f2 = nn.Linear(d, 4 * d), nn.Linear(4 * d, d); s.f3 = nn.Linear(d, d)
    def forward(s, h):
        B, L, _ = h.shape; sp = lambda t: t.view(B, L, 4, 16).transpose(1, 2)
        att = (sp(s.q(h)) @ sp(s.k(h)).transpose(-1, -2)) / 4.0
        att = att.masked_fill(torch.triu(torch.ones(L, L, dtype=torch.bool), 1), -1e9).softmax(-1)
        h = h + a * s.o((att @ sp(s.v(h))).transpose(1, 2).reshape(B, L, d))
        return h + a * (torch.relu(s.f3(h)) if onemat else s.f2(torch.relu(s.f1(h))))
tok, pos = nn.Parameter(torch.randn(V, d)), nn.Parameter(torch.randn(C, d)); blocks = nn.ModuleList(Block() for _ in range(depth)); out = nn.Linear(d, V)
params = [tok, pos] + list(blocks.parameters()); oparams = list(out.parameters())
def fwd(x, keep=False):
    h = tok[x] + pos; hs = []
    for b in blocks:
        h = b(h)
        if keep: h.retain_grad(); hs.append(h)
    top = h[:, -1]
    if base == "finalln": top = nn.functional.layer_norm(top, (d,))
    if base == "bcenter": top = top - top.mean(0, keepdims=True)
    return out(top), top, hs
ce = nn.functional.cross_entropy; rng = np.random.default_rng(10_000 + seed); log = []
for s in range(6001):
    if s % 50 == 0:
        z, _, hs = fwd(X[:256], keep=True); ce(z, Y[:256]).backward()
        rm = lambda t: float(torch.sqrt((t.grad[:, -1] ** 2).sum(1).mean()))
        with torch.no_grad(): tl = float(ce(fwd(X[:2000])[0], Y[:2000]))
        log.append(dict(step=s, train_loss=tl, transport=float(np.log(rm(hs[0]) / max(rm(hs[-1]), 1e-30)))))
        for p in params + oparams: p.grad = None
        if not np.isfinite(tl): break
    if s == 6000: break
    idx = torch.tensor(rng.integers(0, len(X), 64)); z, top, _ = fwd(X[idx]); ce(z, Y[idx]).backward()
    with torch.no_grad():
        lo = 0.05
        if base == "norm": lo *= d / max(float((top ** 2).sum(1).mean()), 1e-12)
        if base == "cap10":
            dz = -lo * (top @ out.weight.grad.T + out.bias.grad); kb = float(torch.sqrt((dz ** 2).sum(1).mean()))
            if kb > 10: lo *= 10 / kb
        for p in params:
            if p.grad is not None: p -= 0.05 * p.grad; p.grad = None  # unused branch weights get no gradient
        for p in oparams: p -= lo * p.grad; p.grad = None
with torch.no_grad(): tloss = float(ce(fwd(Xt)[0], Yt))
o = os.path.join(HERE, "..", "results", "e55", f"tf{depth}_{cond}_s{seed}.json"); os.makedirs(os.path.dirname(o), exist_ok=True)
with torch.no_grad():
    h0 = tok[X[:256]] + pos; hh = h0
    for b in blocks: hh = b(hh)
    top0 = hh[:, -1]; growth = float(top0.norm(dim=1).mean() / h0[:, -1].norm(dim=1).mean()); shared = float(top0.mean(0).norm() ** 2 / (top0 ** 2).sum(1).mean())
json.dump(dict(depth=depth, cond=cond, seed=seed, test_loss=tloss, log=log, final_stream_growth=growth, final_shared_share=shared), open(o, "w")); print(o, log[-1], tloss)
