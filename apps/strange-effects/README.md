# Strange Effects

`index.html` is the Strange Effects app (attractor sonification with particles, guitar-style notes, 5-speaker space and a formula-to-attractor converter).

## Rendering on GitHub

Some systems (for example the 19-variable Fibonacci ring) are too heavy to play live on a phone. The **Strange Effects render** workflow (Actions tab → Strange Effects render → Run workflow) does the work instead:

- **formula**: any formula the app's converter accepts — one variable (`sin(3x)x`), several (`sin(2xy) - cos(yz)`), up to `x19`, or a system written `x1' = …; x2' = …`. Leave empty to use **system**.
- **system**: a built-in system name (`Fibonacci ring`, `Cavity`, `Lorenz-84`, …).
- **tone**, **particles**, **space**, **seconds**: as in the app.

Results appear at `apps/strange-effects/renders/` on the Pages site, newest first, each with video, sound and a short report (exponents, dimension, render speed, loudness).

## How a formula is accepted

The converter only adds a system when chaos is confirmed: the largest Lyapunov exponent agrees at two step sizes, a zero exponent is present (required of any flow) or the system is hyperchaotic, and for three-variable systems the exponents sum to the flow's contraction. Step size is set from how finely the formula ripples. Results that only loop, settle, or run away are reported as such.

`render/engine.js` is extracted from `index.html` at render time (`render/mkengine.py`), so renders always use exactly the app's engine.
