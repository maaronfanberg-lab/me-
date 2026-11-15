# Perennial

A year-long plant grown from the real Mandelbrot set. Viewer: `apps/perennial.html`.

- `engine.py` and `jet.c` find and measure each bud.
- `grow.py` adds 96 buds per calendar day, for 365 days. Late runs catch up to identical bytes.
- `verify.py` runs independent checks. A failure blocks that day's commit.
- `data/` holds one immutable file per day, joined by a SHA-256 chain.

Method, sources and limits: `docs/research/perennial.md`.
