"""The first 300 steps of a 96-layer residual ReLU network on digits, as sound (README section 9).
Usage: python experiments/sonify_shock.py <shock|warmup> out.wav
  shock:  plain SGD, lr 0.05 from the first step (the collapse of experiments 8-12)
  warmup: identical, except the learning rate rises linearly over the first 50 steps (experiment 13)
One voice per residual block, driven only by that block's measured lapse N* (alpha removed, as everywhere in
experiments 8-21), with lapse.sound's mapping: pitch = 330 Hz x 2^(log10 N*), equal amplitudes, first block hard
left, last block hard right. The lapse is logged every 2 steps; each log lasts 0.08 s, so 300 steps last 12 s.
N* is computed as exp(stream_grad + gate) from lapse/probe.py, which equals geometry(...).lapse exactly
(tests/test_sound.py checks this). The logged data are written beside the audio as <out>.json."""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..")); sys.path.insert(0, HERE)
import numpy as np
from probe_run import run
from lapse.sound import render, write_wav

PIECES = {"shock": dict(), "warmup": dict(warmup=50)}
SPL = 0.08


def lapse_history(piece):
    r = run(dict(task="digits", act="relu", depth=96, seed=0, steps=300, log_every=2, layers_every=2, **PIECES[piece]))
    H = np.exp(np.array([e["stream_grad"] for e in r["log"]]) + np.array([e["gate"] for e in r["log"]]))
    return r, H


def main(piece, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)  # fail early, not after training
    r, H = lapse_history(piece)
    write_wav(path, render(H, seconds_per_log=SPL))
    json.dump(dict(piece=piece, config=r["config"], seconds_per_log=SPL, steps=[e["step"] for e in r["log"]],
                   train_loss=[e["train_loss"] for e in r["log"]], lapse=H.tolist(),
                   parts={k: [e[k] for e in r["log"]] for k in ("Tstar", "ln_out", "ln_transport", "ln_gate")}), open(path + ".json", "w"))
    print(f"{path}: {H.shape[0]} logs x {H.shape[1]} voices, {H.shape[0] * SPL:.1f} s; first-block pitch "
          f"{330 * 2 ** np.log10(H[0, 0]):.0f} Hz -> {330 * 2 ** np.log10(H[-1, 0]):.0f} Hz")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
