# RESONATOR Stage T1 — the Superior water tower, struck with a padded mallet (2026-10-12)

Builds on `resonator-water-tower-2026-10-12.md` (dimensions, sources, first acoustic estimates).

## 1. Request
Alex: after the strip, add a virtual water tower modelled on the spheroid tower in Superior, WI, empty, struck
with a humongous padded mallet (thick leather, wool, tightly compressed Styrofoam or rubber).

## 2–3. Evidence
- Everything in the earlier note (CB&I Waterspheroid sizes, Red Deer spheroid, Abaqus Benchmarks 1.4.1, Russell
  1997 on felt, AFM EPS data, the Rangely tank's reverberation).
- **Thin shells of revolution by finite elements, one circumferential harmonic at a time** (Kalnins 1964 is the
  classic reference for the approach): membrane strains after Novozhilov, Donnell-type bending, linear elements
  for the in-surface displacements and Hermite cubics for the normal one (`qa-resonator/tower_fe.py`). Checked
  against the Abaqus sphere benchmark: n = 2, 3, 4, 6 within 0.01%, and with the pole conditions in place the
  lowest mode of each order m on the sphere is the benchmark's n = m (no spurious modes).
- **Ratchet inside the FE work:** the first FE version started the mesh at a tiny free hole at the top. A free edge
  there carries edge modes: it reported a two-lobed mode at 52.0 Hz living on a 0.3 m hole. Pole regularity
  conditions (by m) removed it; the sphere check now also asks for the *lowest* mode per order, not the nearest.

## 4. Findings that shaped the build
1. **The engine's spring law makes a curved shell behave like a membrane shell** (`sphere_check.mjs`): a free
   triangulated sphere with transverse:longitudinal stiffness 1:196 (Stiffness 14) gives n = 3, 4 and breathing
   within 2–3% of the membrane equation, ratios relative to n = 2. Lower Stiffness lets the transverse term lift
   the higher modes. So the tower runs at Stiffness 14.
2. **The mesh has to be near-equilateral.** Rings of equal node count (like the Tank's) shear and spread the
   modes; rings whose node count follows their circumference, stitched into near-equilateral triangles, track the
   membrane equation (n = 3: 1.186 vs 1.184).
3. **The bowl is oblate, and that matters** (FE, 23 × 17.5 m, clamped at the cone neck, 10–25 mm walls):
   - breathing mode 128.7–129.0 Hz for any wall from 10 to 25 mm (it is a membrane mode), volume share 0.90;
   - lowest two-lobed mode 54.5–55.1 Hz;
   - global modes below the cluster: rocking 4.3 Hz, vertical bounce 15 Hz, 40.6 and 47.6 Hz;
   - hundreds of mode shapes from ~55 to ~120 Hz (the flat top, radius of curvature 15 m, sets the bottom of the
     band; the sharply curved shoulder, 6.7 m, the top). The sphere estimates (64–82 Hz) are too narrow.
4. **The tuning reference.** The engine tunes the loudest mode at the strike and mic; on the tower that is often
   a rocking mode of the bowl on its neck (the engine's transverse springs also resist rigid rotation, which a real
   tower does not), so the keys would have tuned the wrong thing. The tower carries a *probe*, the bowl swelling
   outward along its normal; the engine tunes the mode most like it — the breathing mode. At real size that is
   129 Hz, so the real tower plays at C3 (130.8 Hz, −25 cents), and its boom lies about an octave below.
5. **Neck clamped, column separate.** The bowl is clamped where it meets the cone neck and the column is its own
   shell, clamped at the neck and at the ground. This leaves out the tower's sway and the bowl rocking on the
   column (a few Hz at real size: felt, not heard), which this engine cannot model correctly anyway. Striking the
   column rings the column; it does not shake the bowl.
6. **The mallet.** The engine now simulates the strike itself: a 200 kg head at 5 m/s × key strength × Drive
   (key strength 0.8 = 4 m/s) through 8 cm of padding over a 0.6 m face, against a rigid wall, at real size and
   2 µs steps, with the force laws of `tower_acoustics.py`. Its force history becomes the strike, lasting as long
   as it really would at real size and proportionally shorter on a smaller tower (a smaller tower is hit with a
   proportionally smaller mallet). The impulse follows the rebound, m v₀ (1 + e).

## 6–7. Limits and competing explanations
- The mesh carries 3 × 89 degrees of freedom; the real bowl has thousands of modes in its cluster. The model holds
  the low orders (up to 6–8 lobes round). Its cluster median matches the FE's modes of those orders (74 vs 75 Hz)
  and the research table (64–82 Hz), but the model's top of the cluster sits lower than the FE's (90th percentile
  93 vs 112 Hz). Error vs taste: a known limit of the mesh, not a tuning choice.
- The breathing character is spread over two or three neighbouring modes on coarse meshes (Size 10, 12, 16); the
  runner-up always lies within 11% in pitch, so the tuned pitch moves little whichever one wins.
- **Decay.** The engine has one decay rate plus damping that eats the highs. The research's ~3 s for the low bowl
  modes is matched at the default Sustain (60 dB in 3.05 s at real size). The long faint hum of the high-order
  modes (~20 s) needs modes this mesh does not have; a longer Sustain is the stand-in.
- The real tower's dimensions are from photos (±15%); all frequencies scale inversely with size.
- The rubber and leather moduli are assumptions (as in the earlier note); wool's law and the foam's crush stress
  are sourced. A fresh pad is used for every strike (real foam would stay dented).
- **Finding, not changed (taste for Alex):** the Tank plays at −17.0 LUFS as the page drives it, not the −21 its
  calibration aimed for (that was measured without the level trim; see J1). The tower is calibrated to match the
  Tank as it is actually heard (−17.2 LUFS), so switching bodies keeps the loudness.
- **Pre-existing, not changed:** the readout's "reference mode … Hz" is the engine's internal reference at its
  base stiffness, not the pitch you hear (thousands of Hz on both bodies).

## 8. Context transfer
The FE and the mass-spring model are two independent derivations of the same bowl (one a continuum shell, one the
engine's own springs). The mallet numbers are the earlier note's model, now inside the engine, checked equal.

## 9. Implementation mapping (`qa-resonator/patch_t1.py`)
- **Engine (additive; the Tank is bit-identical):** `probe` on a body (normalised overlap per mode; the reference
  is the best overlap); `pad`, `padRef` controls; `padForce`, `padContact`, `padStrike`; strike pulses can carry a
  force table.
- **Page:** `SHAPES.Tower` (Size = nodes round the bowl, 10–18, default 14: 89 masses, 220 springs, about the
  Tank's largest), its defaults (Stiffness 14, Sustain 1.6, keys from E4); Body chips Tank | Water tower; on the
  Strike tab for the tower, Padding chips (Leather, Wool, Styrofoam, Rubber) in place of the Mallet knob, and Real
  size (C3) / Phone size (E4) with a note saying how tall a tower the lowest key plays; the readout shows it too;
  presets for both bodies (the probe is rebuilt on load). Level: `SHAPE_LVL.Tower` 4.45.

## 10. Validation (`t1_verify.mjs`, `t1_browser.py`; WebKit in CI)
| check | result |
|---|---|
| A. Tank bit-identical to the preview before T1 (16 setups, 32 and 48 kHz) | 16/16 |
| B1. keys tune the breathing mode (probe overlap; default Size 32% vs 22% runner-up) | pass; mutation (probe ignored) fails |
| B2. real-size breathing 129 Hz = FE, inside 118–138 | pass |
| B3. lowest two-lobed mode at real size 55–61 Hz across Sizes (table 51–60 ±10%) | pass |
| B4. cluster median 74 Hz (table 64–82; FE same orders 75 Hz) | pass |
| C1. contact vs `tower_acoustics.py`: leather 2.2 ms, wool 24.9 ms, foam 12.2 ms, rubber 12.3 ms; bandwidth and rebound equal | pass; mutation (wool exponent 2.0) fails |
| C2. wool brightens with a harder swing (2→8 m/s: 77→139 Hz); leather does not | pass |
| C3. strike length scales with the tower (real 30.4 ms, half size 15.2 ms) | pass |
| D1. every padding audibly different (≥ 5% brightness or ≥ 1 dB) | pass (closest pair wool/foam 27%) |
| D2. Real size vs Phone size | pass |
| E1. 60 dB fall at real size 3.05 s (research 2.9 s) | pass |
| E2. Sustain readout on the tower | within 25% (shows 2.5 s, measured 2.0 s) |
| F1. loudness: Tower −17.2 vs Tank −17.0 LUFS | pass |
| F2. worst case, every padding, smallest and largest tower | peak ≤ 0.767, no NaN |
| F3. deterministic | pass |
| G1. cost: 220 springs × 1 (Tank largest 216) | pass |
| browser: tower by a tap, defaults, label, probe sent, plays; each padding by a tap; Real/Phone size; Size; strike circle on the bowl; presets round trip; back to the Tank | all pass (Chromium here; WebKit on Linux and macOS in CI) |
| existing suites (Stage 1, P1, I, J1, WebKit check) on the new page | pass |

**Post-change result after deployment:** pending Alex.
- Does it sound like a water tower being hit? Which padding is right?
- Real size on headphones; Phone size on the phone speaker.
- Is the tower the body the page should open on?
