# Room successor: live Allen direct-address and active-task responsiveness

Date: 2026-11-17. Status: **isolated code/test result; no behavioral release evidence**.
Branch: `experiment/relationship-centered-agents-20261115`, draft PR #415.

## Grounded frozen observational baseline

At 2026-11-17 12:06:17 UTC, production `room/feed.json` and
`room/state.json` agreed at cycle **70,634**. Retrieved Git blob SHA values:
- `room/feed.json`: `0fad88d6ab6c1d07c410315283bf69951dc0a81d`
- `room/state.json`: `8737009cca522d4b826d50506778cfc60a7cbd7f`

The last 160 public feed turns contained 132 intention-pattern turns
(ad hoc regex with decide/choose/plan/want/will/going to/I'll variants),
54 notebook references, four question-mark turns, and two new Allen turns.
One was the direct request `Owen. Please read me the 128 written pages`
(event `20261117T115445607-allen-v5-d05d69466d` at 11:54:45 UTC).
At the pinned snapshot, there was no subsequent published character response.
That fact does **not** prove the production agent saw the message: delivery
acknowledgement is governed by a separate relay, and active inference logs
were not available. A later Allen turn is omitted here because it is not
needed to reproduce the address-routing defect.

Production was still Concordia `room-cognition-v5`, with eleven silent
cycles on the initial 12:02 UTC inspection and fourteen by 12:06 UTC.
At 12:06 the scheduler had zero queued events/steps; no accepted new
Allen input was recorded **in that particular cycle**. This is not proof
there were no earlier incoming Allen messages.

## Falsifiable defects and pre-registered acceptance criteria

**H1: busy-agent reply starvation.** Prior experimental
`room_social_decision.decide` returned `observe` on a grounded,
witnessed, explicitly addressed reply proposal whenever `active_task`
was truthy. This conflicts with the scenario specified in
`docs/room-karpathy-source-map.md`. Expected: return a reply decision
without modifying the unfinished task. Negative controls: absent proposal,
acknowledged input, private unwitnessed input, colliding event IDs, and
competing new work while occupied.

**H2: period vocative routing.** Prior `room_social_joint_context`
recognized `Owen,` but not the actually observed `Owen.` because its
name-delimiter class was `[,!?]`. That caused an addressed public Allen
message to be offered as a broadcast opportunity. Expected: only Owen
receives the directed bid; an ordinary mention such as `Owen's notebook`
is not treated as an address. Unknown private visibility must fail closed.

**H3: disconnected policy pipeline.** The existing decision gate expected
`addresses` and explicit `visibility`, but historic public feed events
lack those fields. Expected: a read-only bridge derives evidence-linked
address opportunities through the existing witnessed-history compiler,
sets public visibility only when *absent* on legacy public feed rows,
retains explicit restrictions and detects duplicate IDs. A reply still
requires a separately supplied nonempty proposal. No generated speech
or world action may be fabricated.

Primary design motivation: Park et al. (2023) *Generative Agents*
(memory/reflection/planning with grounded outcomes); *Humanoid Agents*
(2023) (individual needs and relational context); and *SOTOPIA*
(2024) (interactive social competence is hard to establish).
Methods: the six original Karpathy sources mapped in
`docs/room-karpathy-source-map.md`; specifically autoresearch's frozen
comparison protocol and micrograd/llm.c's independent correctness checks.
These sources inform tests, not claims that experimental behavior is human.

## Implemented on isolated PR #415

- `0da1dc0`, `0b6c0f6`: allow grounded witnessed replies while keeping
  active tasks; test privacy, silence, acknowledgements and continuity.
- `44fbc19`, `71141cb`: include a period in explicit vocative parsing;
  test the exact real-world Allen phrase and unrelated-mention controls.
- `871f167`, `2eaa89a`: add `decide_from_history` to join witnessed
  legacy feed opportunities with pre-existing agent proposals; tests include
  actual event ID, unfinished Owen task, acknowledgements, privacy and
  duplicate-event collisions.

CI completed successfully for the first two change pairs:
- 62/62 tests: https://github.com/maaronfanberg-lab/me-/actions/runs/44079658110
- 63/63 tests: https://github.com/maaronfanberg-lab/me-/actions/runs/44079936961

The final bridge's CI result is recorded by GitHub for commit
`2eaa89aea274cb083efcd2f5170924943a2c90e6`; check the live run
before stating its outcome.

## Hard limitations and release gate

These tests verify deterministic eligibility decisions, not model-generated
replies, published messages, trust of referee records, relationship quality,
or real responsiveness in production. **No matched same-snapshot baseline
versus candidate LLM trajectory has been executed**. No live character memory
or production writer was changed. Do not merge or cut over until an
independently verifiable full sequence demonstrates a real proposal,
delivered witnessed response, intact unfinished work, referee-confirmed
consequence, and satisfactory privacy, intentional-silence, and duplicate
controls with production-safe rollback.
