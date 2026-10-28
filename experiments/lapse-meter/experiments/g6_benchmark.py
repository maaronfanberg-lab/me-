"""G6A locked optimizer screening benchmark. See GAUGE_G6A_PREREGISTRATION.md.

Run: OPENBLAS_NUM_THREADS=1 python experiments/g6_benchmark.py results/g6a/results.json
Uses sklearn bundled data, existing numpy MLP and frozen G5 frame_step.
"""
import copy
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np
from sklearn.datasets import load_digits, load_wine
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from lapse.nets import MLP, SGD
from g5_frame import frame_step
from g4_trajectory import scales
from g2_gauge_invariants import reparameterize

TASKS = ('digits', 'wine', 'circle')
ARCHITECTURES = (('plain', 8), ('residual', 24))
RATES = {'sgd': (0.01, 0.05, 0.1),
         'adam': (0.0003, 0.001, 0.003),
         'g5': (0.01, 0.03, 0.05)}
TUNE_SEEDS = (20, 21)
TEST_SEEDS = (30, 31, 32, 33, 34)
STEPS = 200
BATCH = 64
CHECKPOINTS = (0, 1, 50, 100, 200)


class Adam:
    """Standard bias-corrected Adam, beta=(.9,.999), epsilon=1e-8."""
    def __init__(self, net, lr):
        self.lr, self.t = lr, 0
        self.m = [np.zeros_like(p) for p in net.W + net.b]
        self.v = [np.zeros_like(p) for p in net.W + net.b]

    def step(self, net, gw, gb):
        self.t += 1
        for i, (p, g) in enumerate(zip(net.W + net.b, gw + gb)):
            self.m[i] = .9 * self.m[i] + .1 * g
            self.v[i] = .999 * self.v[i] + .001 * (g * g)
            mh = self.m[i] / (1 - .9 ** self.t)
            vh = self.v[i] / (1 - .999 ** self.t)
            p -= self.lr * mh / (np.sqrt(vh) + 1e-8)


def dataset(task, seed):
    if task == 'digits':
        X, y = load_digits(return_X_y=True)
    elif task == 'wine':
        X, y = load_wine(return_X_y=True)
    elif task == 'circle':
        r = np.random.default_rng(500_000 + seed)
        X = r.uniform(-1., 1., size=(1800, 2))
        y = (np.sum(X * X, axis=1) < 0.55 ** 2).astype(int)
    else:
        raise ValueError(task)
    X = np.asarray(X, dtype=np.float64)
    y = np.asarray(y, dtype=np.int64)
    ids = np.arange(len(y))
    work, test = train_test_split(ids, test_size=.20, random_state=seed, stratify=y)
    train, val = train_test_split(work, test_size=.25, random_state=seed + 1, stratify=y[work])
    assert not (set(train) & set(val) or set(train) & set(test) or set(val) & set(test))
    scaler = StandardScaler().fit(X[train])
    scaled = scaler.transform(X)
    assert np.isfinite(scaled).all()
    parts = tuple((scaled[z], y[z]) for z in (train, val, test))
    return parts, dict(n_train=len(train), n_val=len(val), n_test=len(test),
                       classes=int(y.max() + 1))


def train_one(task, architecture, depth, optimizer, lr, seed, gauge=False):
    (tr, va, te), meta = dataset(task, seed)
    X, y = tr
    model = MLP(X.shape[1], 64, depth, meta['classes'],
                act='relu', residual=architecture == 'residual', seed=seed)
    if gauge:
        d = scales(model, 'neuronwise', seed)
        model = reparameterize(model, d)
    else:
        d = None
    opt = SGD(lr) if optimizer == 'sgd' else Adam(model, lr) if optimizer == 'adam' else None
    batches = np.random.default_rng(10_000 + seed)
    snapshots = []
    t0 = time.perf_counter()
    failed = None
    for step in range(STEPS + 1):
        if step in CHECKPOINTS:
            try:
                snapshots.append(dict(step=step, train_loss=model.loss(*tr),
                                      val_loss=model.loss(*va), test_loss=model.loss(*te),
                                      test_accuracy=model.accuracy(*te)))
                if not np.isfinite([snapshots[-1]['train_loss'], snapshots[-1]['val_loss'], snapshots[-1]['test_loss']]).all():
                    raise FloatingPointError('nonfinite logged loss')
            except (ValueError, FloatingPointError, OverflowError) as exc:
                failed = f'checkpoint {step}: {type(exc).__name__}: {str(exc)[:120]}'
                break
        if step == STEPS:
            break
        ix = batches.integers(0, len(X), BATCH)
        try:
            if optimizer == 'g5':
                frame_step(model, X[ix], y[ix], eta=lr, cap=1.)
            else:
                _, gw, gb, _ = model.backward(X[ix], y[ix])
                if not all(np.isfinite(g).all() for g in gw + gb):
                    raise FloatingPointError('nonfinite gradient')
                opt.step(model, gw, gb)
            if not all(np.isfinite(p).all() for p in model.W + model.b):
                raise FloatingPointError('nonfinite parameters')
        except (ValueError, FloatingPointError, OverflowError) as exc:
            failed = f'update {step+1}: {type(exc).__name__}: {str(exc)[:120]}'
            break
    elapsed = float(time.perf_counter() - t0)
    record = dict(task=task, architecture=architecture, depth=depth, method=optimizer,
                  lr=lr, seed=seed, gauge=bool(gauge), elapsed_s=elapsed,
                  failed=failed, snapshots=snapshots, dataset=meta)
    return record, model


def final_metric(record, key):
    if record['failed'] or not record['snapshots'] or record['snapshots'][-1]['step'] != STEPS:
        return float('inf')
    return record['snapshots'][-1][key]


def choose_rates(tuning):
    selected = []
    for task in TASKS:
        for architecture, depth in ARCHITECTURES:
            for method, rates in RATES.items():
                rows = [r for r in tuning if (r['task'], r['architecture'], r['method']) == (task, architecture, method)]
                candidates = []
                for lr in rates:
                    cells = [r for r in rows if r['lr'] == lr]
                    assert len(cells) == len(TUNE_SEEDS)
                    vals = [final_metric(r, 'val_loss') for r in cells]
                    avg = float(np.mean(vals)) if all(np.isfinite(vals)) else float('inf')
                    candidates.append(dict(lr=lr, mean_val_loss=avg if np.isfinite(avg) else None,
                                           failures=sum(r['failed'] is not None for r in cells)))
                best = min(candidates, key=lambda c: (c['failures'],
                              float('inf') if c['mean_val_loss'] is None else c['mean_val_loss'], c['lr']))
                selected.append(dict(task=task, architecture=architecture, depth=depth,
                                     method=method, selected_lr=best['lr'], candidates=candidates))
    return selected


def gauge_comparison(normal, transformed, task, architecture, method, seed):
    if normal['failed'] or transformed['failed']:
        return dict(task=task, architecture=architecture, method=method, seed=seed,
                    max_logit_diff=None, all_checkpoints_match=False,
                    failed=True, checkpoints=[])
    checkpoints = []
    # Each recorded snapshot's losses and accuracies are obtained from the same held-out set.
    for a, b in zip(normal['snapshots'], transformed['snapshots']):
        assert a['step'] == b['step']
        checkpoints.append(dict(step=a['step'], test_loss_difference=abs(a['test_loss']-b['test_loss']),
                                test_accuracy_equal=a['test_accuracy'] == b['test_accuracy']))
    return dict(task=task, architecture=architecture, method=method, seed=seed,
                # For exact logits, run matched paired trajectories in dedicated gauge_test().
                loss_gap=max(x['test_loss_difference'] for x in checkpoints),
                accuracy_match=all(x['test_accuracy_equal'] for x in checkpoints),
                failed=False, checkpoints=checkpoints)


def gauge_test(task, architecture, depth, method, lr, seed):
    (tr, _, te), meta = dataset(task, seed)
    X, y = tr
    a = MLP(X.shape[1], 64, depth, meta['classes'], act='relu', residual=architecture == 'residual', seed=seed)
    b = reparameterize(a, scales(a, 'neuronwise', seed))
    oa = SGD(lr) if method == 'sgd' else Adam(a, lr) if method == 'adam' else None
    ob = SGD(lr) if method == 'sgd' else Adam(b, lr) if method == 'adam' else None
    rng = np.random.default_rng(10_000 + seed)
    vals = []
    failed = None
    for step in range(STEPS + 1):
        if step in CHECKPOINTS:
            try:
                la, lb = a.forward(te[0])[1][-1], b.forward(te[0])[1][-1]
                d = float(np.max(np.abs(la-lb)))
                acca, accb = a.accuracy(*te), b.accuracy(*te)
                vals.append(dict(step=step, max_logit_difference=d,
                                 accuracy_match=acca == accb,
                                 test_loss_difference=abs(a.loss(*te)-b.loss(*te))))
                if not np.isfinite([d, vals[-1]['test_loss_difference']]).all():
                    raise FloatingPointError('nonfinite gauge-check output')
            except (ValueError, FloatingPointError, OverflowError) as exc:
                failed = f'checkpoint {step}: {type(exc).__name__}: {str(exc)[:120]}'
                break
        if step == STEPS:
            break
        ix = rng.integers(0, len(X), BATCH)
        try:
            for n, opt in ((a, oa), (b, ob)):
                if method == 'g5':
                    frame_step(n, X[ix], y[ix], eta=lr, cap=1.)
                else:
                    _, gw, gb, _ = n.backward(X[ix], y[ix])
                    if not all(np.isfinite(g).all() for g in gw+gb):
                        raise FloatingPointError('nonfinite gauge gradient')
                    opt.step(n, gw, gb)
                if not all(np.isfinite(p).all() for p in n.W+n.b):
                    raise FloatingPointError('nonfinite gauge parameters')
        except (ValueError, FloatingPointError, OverflowError) as exc:
            failed = f'update {step+1}: {type(exc).__name__}: {str(exc)[:120]}'
            break
    return dict(task=task, architecture=architecture, method=method, seed=seed, rate=lr,
                gauge='neuronwise_1/8_to_8', failed=failed, checkpoints=vals,
                max_logit_difference=max((r['max_logit_difference'] for r in vals), default=None),
                all_checkpoints_match=(failed is None and len(vals)==len(CHECKPOINTS) and
                   all(r['max_logit_difference'] < 1e-7 and r['accuracy_match'] and
                       r['test_loss_difference'] < 1e-9 for r in vals)))


def summary(selected, evaluation, gauge):
    cells = []
    for task in TASKS:
        for arch, depth in ARCHITECTURES:
            stats = {}
            for method in RATES:
                v = [r for r in evaluation if (r['task'], r['architecture'], r['method']) == (task, arch, method)]
                assert len(v) == len(TEST_SEEDS)
                losses = [final_metric(r, 'test_loss') for r in v]
                acc = [final_metric(r, 'test_accuracy') for r in v]
                failures = sum(r['failed'] is not None for r in v)
                stats[method] = dict(failures=failures,
                         mean_test_loss=float(np.mean(losses)) if all(np.isfinite(losses)) else None,
                         mean_test_accuracy=float(np.mean(acc)) if all(np.isfinite(acc)) else None,
                         sd_test_accuracy=float(np.std(acc, ddof=1)) if all(np.isfinite(acc)) else None,
                         median_runtime_s=float(np.median([r['elapsed_s'] for r in v])))
            winning = (stats['g5']['mean_test_loss'] is not None and
                       all(stats['g5']['mean_test_loss'] <= stats[b]['mean_test_loss']
                           for b in ('sgd', 'adam') if stats[b]['mean_test_loss'] is not None) and
                       all(stats[b]['mean_test_loss'] is not None for b in ('sgd','adam')))
            cells.append(dict(task=task, architecture=arch, depth=depth, metrics=stats,
                              g5_beats_both=bool(winning)))
    checks = [r for r in gauge if r['method']=='g5']
    return dict(primary_gauge_pass=(len(checks)==30 and all(r['all_checkpoints_match'] for r in checks)),
                g5_wins=int(sum(c['g5_beats_both'] for c in cells)),
                directional_h2_pass=(sum(c['g5_beats_both'] for c in cells)>=4),
                cells=cells)


def run():
    tuning=[]
    for task in TASKS:
        for arch, depth in ARCHITECTURES:
            for method, lrs in RATES.items():
                for lr in lrs:
                    for seed in TUNE_SEEDS:
                        r,_ = train_one(task, arch, depth, method, lr, seed)
                        tuning.append(r)
                print('TUNE',task,arch,method,'complete',flush=True)
    selected = choose_rates(tuning)
    evaluation=[]; gauge=[]
    for c in selected:
        for seed in TEST_SEEDS:
            args=(c['task'],c['architecture'],c['depth'],c['method'],c['selected_lr'],seed)
            r,_=train_one(*args)
            evaluation.append(r)
            g=gauge_test(*args)
            gauge.append(g)
        print('HOLDOUT',c['task'],c['architecture'],c['method'],
              'rate',c['selected_lr'],flush=True)
    report = dict(protocol='G6A',n_tuning=len(tuning),n_evaluation=len(evaluation),
                  n_gauge=len(gauge),dataset_protocol='stratified60/20/20; train-only StandardScaler',
                  tuning=tuning,selected=selected,evaluation=evaluation,gauge=gauge)
    report['summary']=summary(selected,evaluation,gauge)
    return report


if __name__=='__main__':
    outfile=sys.argv[1] if len(sys.argv)>1 else 'results/g6a/results.json'
    os.makedirs(os.path.dirname(os.path.abspath(outfile)),exist_ok=True)
    result=run()
    with open(outfile,'w') as f:
        json.dump(result,f,indent=2,allow_nan=False)
    print('G6A SUMMARY',json.dumps(result['summary'],indent=2),flush=True)
    print('Saved',outfile,flush=True)
