"""Synthetic unit checks for Gauge G1. Run python tests/test_g1_gauge.py."""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "experiments"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import numpy as np
from lapse.nets import MLP
from g1_gauge import compare, rescale_residual_stream, rescale_plain_layer

rng = np.random.default_rng(13)
X = rng.standard_normal((37, 7))
y = rng.integers(0, 4, 37)
checks = 0
for residual in (True, False):
    for signed in ((False, True) if residual else (False,)):
        net = MLP(7, 12, 6, 4, act="relu", residual=residual, seed=8, branch_sign=signed)
        for c in (0.25, 1.0, 4.0, 1024.0):
            r = compare(net, X, y, c)
            assert r["max_logit_difference"] < 1e-9
            assert r["tilt_identity_error"] < 1e-9
            checks += 1
        before = net.forward(X)[1][-1].copy()
        _ = rescale_residual_stream(net, 4) if residual else rescale_plain_layer(net, 4)
        assert np.array_equal(net.forward(X)[1][-1], before)
        checks += 1
for fn, kw in ((rescale_residual_stream, {"residual": True}), (rescale_plain_layer, {"residual": False})):
    net = MLP(7, 12, 6, 4, act="tanh", seed=3, **kw)
    try:
        fn(net, 4)
        raise AssertionError("tanh should not be accepted as positively homogeneous")
    except ValueError:
        checks += 1
print(f"PASS {checks} G1 invariance and rejection checks")
