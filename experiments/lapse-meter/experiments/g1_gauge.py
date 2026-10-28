"""Gauge G1: function-preserving ReLU rescalings versus lapse.
Run from lapse-meter root: python experiments/g1_gauge.py results/g1/gauge.json
Protocol: GAUGE_G1_PREREGISTRATION.md. Does not modify old experiments.
"""
import copy
import json
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from lapse import geometry
from lapse.data import digits
from lapse.nets import MLP, SGD

SCALES = (0.25, 1.0, 4.0, 1024.0)


def rescale_residual_stream(net, c):
    """For residual ReLU, h0 and every residual stream h_i -> c*h_i; logits unchanged."""
    if not (net.residual and net.act == "relu" and np.isfinite(c) and c > 0):
        raise ValueError("requires residual ReLU and finite c>0")
    other = copy.deepcopy(net)
    other.W[0] *= c
    other.b[0] *= c
    for i in range(1, len(other.W) - 1):
        other.b[i] *= c
    other.W[-1] /= c
    return other


def rescale_plain_layer(net, c, layer=0):
    """For plain ReLU, W_l,b_l *= c; W_(l+1) /= c; logits unchanged."""
    if not (not net.residual and net.act == "relu" and np.isfinite(c) and c > 0):
        raise ValueError("requires plain ReLU and finite c>0")
    if not 0 <= layer < len(net.W) - 1:
        raise ValueError("layer must be hidden")
    other = copy.deepcopy(net)
    other.W[layer] *= c
    other.b[layer] *= c
    other.W[layer + 1] /= c
    return other


def read(net, X, y):
    bw = net.backward(X, y)
    corrected = geometry(net.geometry_deltas(bw[3], remove_alpha=True))
    raw = geometry(net.geometry_deltas(bw[3]))
    return dict(logits=net.forward(X)[1][-1], loss=net.loss(X, y),
                accuracy=net.accuracy(X, y), corrected=corrected, raw=raw,
                weight_grads=bw[1])


def compare(net, X, y, c):
    residual = net.residual
    trial = rescale_residual_stream(net, c) if residual else rescale_plain_layer(net, c)
    a, b = read(net, X, y), read(trial, X, y)
    dt = b["corrected"].tilt - a["corrected"].tilt
    block_err = None
    if residual:
        block_err = max(float(np.max(np.abs(a["weight_grads"][i]-b["weight_grads"][i])))
                        for i in range(1, len(net.W)-1))
    out = dict(architecture="residual" if residual else "plain",
               depth=len(net.W)-1, scale=c,
               max_logit_difference=float(np.max(np.abs(a["logits"]-b["logits"]))),
               loss_difference=float(abs(a["loss"]-b["loss"])),
               accuracy_before=a["accuracy"], accuracy_after=b["accuracy"],
               tilt_before=a["corrected"].tilt, tilt_after=b["corrected"].tilt,
               tilt_change=dt, expected_tilt_change=float(-np.log(c)),
               tilt_identity_error=float(abs(dt+np.log(c))),
               raw_tilt_change=b["raw"].tilt-a["raw"].tilt,
               slope_before=a["corrected"].kappa, slope_after=b["corrected"].kappa,
               horizons_before=len(a["raw"].horizons),
               horizons_after=len(b["raw"].horizons),
               residual_weight_gradient_difference=block_err)
    assert np.isfinite(list([out["max_logit_difference"], out["loss_difference"], out["tilt_identity_error"]])).all()
    assert out["max_logit_difference"] < 1e-9, out
    assert out["loss_difference"] < 1e-9, out
    assert out["accuracy_before"] == out["accuracy_after"], out
    assert out["tilt_identity_error"] < 1e-9, out
    if residual:
        assert abs(out["slope_after"]-out["slope_before"]) < 1e-9, out
        assert block_err < 1e-9, out
    return out


def train(net, X, y, steps, seed):
    opt = SGD(0.05)
    rng = np.random.default_rng(10_000+seed)
    for _ in range(steps):
        idx = rng.integers(0, len(X), 64)
        _, gw, gb, _ = net.backward(X[idx], y[idx])
        opt.step(net, gw, gb)


def run(steps=500, seeds=(0, 1)):
    records = []
    for seed in seeds:
        X, y, Xt, yt = digits(seed)
        for residual, depth in ((True, 24), (False, 8)):
            net = MLP(X.shape[1], 64, depth, 10, act="relu", residual=residual, seed=seed)
            acc_initial = net.accuracy(Xt, yt)
            train(net, X, y, steps, seed)
            acc_final = net.accuracy(Xt, yt)
            for c in SCALES:
                r = compare(net, X[:256], y[:256], c)
                r.update(seed=seed, steps=steps,
                         test_accuracy_initial=acc_initial, test_accuracy_trained=acc_final)
                records.append(r)
                print(f"{'res' if residual else 'plain'} d{depth} seed={seed} c={c:g}: "
                      f"|logits|={r['max_logit_difference']:.2e}, "
                      f"dT={r['tilt_change']:+.4f}, "
                      f"horizons={r['horizons_before']}->{r['horizons_after']}", flush=True)
    return dict(experiment="G1", scales=SCALES, records=records,
                all_identities_held=True,
                any_horizon_changed=any(r["horizons_before"] != r["horizons_after"] for r in records))


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(__file__), "..", "results", "g1", "gauge.json")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    result = run()
    assert result["any_horizon_changed"], "no numerical horizon threshold crossed"
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
    print("PASS G1 all identities; horizon threshold changed:", result["any_horizon_changed"])
