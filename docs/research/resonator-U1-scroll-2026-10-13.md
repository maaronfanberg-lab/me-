# RESONATOR Stage U1 — scrolling over the controls no longer moves them (2026-10-13)

## 1. Observed problem
Alex, on his iPhone (preview, 2026-10-13): "when I try to scroll the sliders often get activated. It's hard to do
even when I put my finger in the in between spaces." "Very hard to use."

Cause, from the code:
- Every slider bar acted on `touchstart` (the value jumped to the finger), called `preventDefault()`, and had
  `touch-action: none`. The − / + buttons started stepping on `touchstart` and also called `preventDefault()`.
- So a scroll that began on a control changed it and could not scroll. Bars and buttons are 42 px tall and fill
  each row; the gaps between rows are 10 px, so most of the panel was a trap.
- The label's double-tap reset fired on any two touch-downs within 400 ms (scrolling flicks included).

Reproduced before the fix (`u1_browser.py` on the old page): 108 vertical swipes starting on controls; values moved
on them, and 0 of 81 swipes with room to scroll scrolled the panel.

## 2–3. Evidence
- **Touch slop.** Android's gesture guide: touch slop is "the distance in pixels a user's touch can wander before the
  gesture is interpreted as scrolling", "used to prevent accidental scrolling when the user is performing another
  touch operation"; a parent takes the gesture as a scroll only once the finger has moved past the slop, otherwise
  the child keeps it ([Manage touch events in a ViewGroup](https://developer.android.com/training/gestures/viewgroup);
  `ViewConfiguration.getScaledTouchSlop()`, 8 dp).
- **`touch-action`** tells the browser up front which gestures it may handle; `pan-y` keeps single-finger vertical
  panning for the browser, and the property should be set because the browser decides before any listener runs
  ([MDN, touch-action](https://developer.mozilla.org/Web/CSS/touch-action); Baseline, widely available since 2019).
  Exact iOS version support for `pan-y` was not confirmed from the page; the design does not depend on it alone
  (the listeners are passive until a drag is decided, so the browser is free to scroll either way).

## 5. Mechanism
A touch on a control is undecided until it moves 10 CSS px (a little more than 8 dp, for a resting thumb) or lifts:
- bar: sideways (|dx| > 1.5 |dy|) = a slider drag from then on; any other way = a scroll, left to the page; lifted
  within 10 px and 500 ms = a tap, which sets the value where the finger landed;
- − / +: lifted without moving = one step; held still 400 ms = repeat (as before); moved = a scroll, nothing;
- label: double-tap reset counts `click` events only, which a scroll never produces.
Mouse and pen act at once, as before; pointer events of type touch are ignored, so a touch is handled once.

## 6–7. Competing explanations, limits
- A tap on a bar still sets the value (Alex's standing rule: every control needs a tap path). A deliberate resting
  touch that lifts without moving is a tap.
- A slider drag now needs 10 px of sideways movement before it starts (the value then jumps to the finger).
- Chromium's emulated touch is not iOS. Playwright cannot touch-drag in WebKit, so swipes are checked in Chromium and
  taps in both; Alex's phone is the final check.
- The old label misfire could not be reproduced in Chromium; that part rests on the design.

## 9. Implementation mapping (`qa-resonator/patch_u1.py`, page only, engine untouched)
`.bar` and `.step` CSS (`touch-action: pan-y`, no `:active` flash while a scroll passes); `attachDrag()` touch
handlers; the knob builder's − / + handlers and label reset; `TOUCH_SLOP`, `HOLD_MS`; Copy report counts scrolls
ignored.

## 10. Validation (`u1_browser.py`)
| check | before | after |
|---|---|---|
| 108 vertical swipes starting on every bar, −, + (all tabs, both ways): no value moves | values moved | none moved |
| …and the panel scrolls where it had room | 0/81 | 81/81 |
| diagonal mostly-vertical swipe; quick short flicks on a bar | moved | nothing |
| sideways drag follows the finger; tap on bar sets; tap on ± one step; hold repeats; label double tap resets; two quick flicks over a label do not; mouse drags | — | pass |
| existing suites (Stage 1, P1, I, T1, WebKit check) | — | pass |

**Post-change result after deployment:** pending Alex — can he scroll the panel with his thumb anywhere?
