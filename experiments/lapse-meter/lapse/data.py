"""Datasets available offline: sklearn's bundled handwritten digits, and a noisy two-ring circle."""
import numpy as np


def digits(seed=0, n_train=1400):
    from sklearn.datasets import load_digits
    d = load_digits()
    X = d.data / 16.0
    X = (X - X.mean(0)) / (X.std(0) + 1e-8)
    y = d.target.copy()
    p = np.random.default_rng(seed).permutation(len(X))
    X, y = X[p], y[p]
    return X[:n_train], y[:n_train], X[n_train:], y[n_train:]


def circle(seed=0, n=1000, noise=0.15):
    r = np.random.default_rng(seed)
    inner = np.arange(n) < n // 2
    rad = np.where(inner, r.random(n) * 2.5, 3.5 + r.random(n) * 1.5)
    ang = r.random(n) * 2 * np.pi
    x, y_ = rad * np.sin(ang), rad * np.cos(ang)
    jx, jy = (r.random(n) * 2 - 1) * 5 * noise, (r.random(n) * 2 - 1) * 5 * noise
    lab = (np.hypot(x + jx, y_ + jy) < 2.5).astype(int)
    X = np.stack([x / 5, y_ / 5], 1)
    p = r.permutation(n)
    X, lab = X[p], lab[p]
    h = n // 2
    return X[:h], lab[:h], X[h:], lab[h:]
