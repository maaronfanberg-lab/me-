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

## Independently checked referee provenance: H4

**Defect:** the actual persistent `room_life` referee emitted
`work_started` and `work_completed` without a shared, independently
issued causal identifier. The isolated receipt verifier therefore could not
authenticate an actual transition, even though its hand-built test fixtures
contained apparently valid provenance. This is the missing causal link, not
a failure of lexical scoring.

**Pre-registered acceptance tests** were committed *before* the repair
(`f51ae45aec114fc25fa99a384cb3bdaf717a8433`):
- A valid, controlled work request gets a referee-issued start event ID.
- No completion receipt exists at start or before the requisite ticks.
- Completion carries matching actor, verb, object and start-event ID.
- A replay of the same cycle never double-applies the task.
- A legacy task whose original start was not provable still completes
  normally, but receives no invented causal receipt.
- All privacy, duplicate, Allen-reply and intentional-quiet suites remain green.

The pre-fix CI run
https://github.com/maaronfanberg-lab/me-/actions/runs/44080852573
**failed as expected** with `KeyError: 'source_decision_id'` in the new
causal test. No production runner was altered.

Repair `79a36ee313e5084f930ddb8e59ffdec2fa10d51a` is limited to
`scripts/room_life.py` on the isolated branch. The referee now issues an
identity on accepted `work_started`, records it on the active task, and
attaches it to a later `work_completed` event **only after verifying the
matching original start**. It does not trust a model-supplied source ID,
reset old tasks, or claim that historical completions have provenance.

The repaired
https://github.com/maaronfanberg-lab/me-/actions/runs/44080969729
passed **67/67** experimental tests, including both new causal tests.
An additional upstream-Concordia integration workflow may run separately;
its result must be verified before claiming integration compatibility.

This is a deterministic referee correctness result, **not a validated
multi-agent conversation**, and no same-snapshot candidate-versus-production
LLM rollout is represented as having happened.


## Actual native beat input-boundary experiment (2026-11-17 23:26–23:34 UTC)

This is a new mechanism, NOT a repetition of the earlier reply-policy or
vocative-regex fixes. Those gates recognized the directed Allen bid but were
not connected to the native Concordia decision context. The live adapter's
`seen_allen_messages` transport checkpoint was updated after delivering a
one-time interrupt, regardless of subsequent publication. This creates a
specific opportunity for a silent interval to consume a request without any
durable, agent-visible *unanswered* request at the next decision.

Pinned observational snapshot (read before code edits):
- live `room/feed.json` blob `a05402980ea4dcbab53da5021ad3d927009a9aeb`
- live `room/state.json` blob `53b35ea5b4cf6fa7945e631abfd480f4669860b2`
- cycle 71240, generated 2026-11-17 23:26:51 UTC; 13 silent cycles,
  scheduler zero queued events; directed Allen request from 11:54:45
  remains in the 160-entry public feed without a demonstrable response
- current production job 134283437990 was `in_progress` when sampled;
  no restart or competing runner was initiated.

**Falsifiable hypothesis:** A request reaches the one-time transport but
is absent from the future per-agent context after a silent beat. Fixing that
context gap should preserve Owen's original witnessed text and ID across two
real scripted native-engine beats even after `seen_allen_messages` contains
the ID. It must not reach Sarah/Mara/Jules, and duplicate IDs, unknown/private
visibility, unlinked talk and unauthorized private replies must not create a
false resolution. Quiet decisions remain valid; no reply is scripted.

**Pre-fix test commit:** `226d874a`. Native CI
https://github.com/maaronfanberg-lab/me-/actions/runs/44200153332
**failed as expected**: 12 `test_room_concordia_live` tests; 1
assertion failure showed the actual Owen decision context lacked the
accepted Allen ID and message, and 2 errors exposed the deliberately
absent pending-social-context method. The upstream native-engine core
nine-test suite still passed. This is a genuine red integration result.

**Narrow isolated implementation:** `c3d7e695` modifies
`scripts/room_concordia_live.py` to compute independently witnessed,
unresolved *direct* Allen bids from existing public conversation through
`room_social_joint_context.joint_context`, exclude colliding IDs, and
include a clearly tagged nonbinding source-ID-bearing social section in
only that addressee's actual native decision context. The physical
world section retains its independent provenance. The context is
reconstructed each beat without marking it fulfilled when the transport
marks it seen. No character is forced to speak and no claim of reading
the pages is authored. `8c406dc0` corrects formatting of section
separators and literal newline handling.

**Green verification:** Native Concordia integration CI
https://github.com/maaronfanberg-lab/me-/actions/runs/44200260596
passed after the targeted implementation: all 12 bridge tests, including
the two-beat real engine test and negative controls, as well as the
nine-test upstream-native engine suite and other world-life regression
suites. Experimental relationship-centered CI
https://github.com/maaronfanberg-lab/me-/actions/runs/44200260615
passed. The latter results are before the formatting-only commit;
recheck CI at the latest head before considering further work.

**Measured improvement:** accepted previously one-shot Allen request
is present in Owen's context on both scripted beats, while absent from
the other characters' contexts. A genuine published Owen response,
completed reading, 160-turn same-model replay, blinded comparative
social review, and durable commitment after the conversation retention
window have **NOT** been verified. This is an engineering input-boundary
repair, not a proven improvement in social intelligence. Do not merge
or cut over on these tests alone.

Research interpretation: Park et al. *Generative Agents* motivates
keeping autobiographical evidence retrievable over multiple decisions;
SOTOPIA shows that attention-path correctness is not equivalent to
social competence. The six Karpathy engineering sources in
`docs/room-karpathy-source-map.md` motivate fixed evidence and
independent red/green verification, not replacing character memory
with a global prompt or automatically promoting the candidate.


## 2026-11-18 01:22 UTC — Feed-eviction persistence experiment

**Distinct from earlier work:** the previous `_social_context` patch made a
public Allen request visible across consecutive *silent* native decisions
only while the request remained in `conversation.json`. It did not survive
eviction from the rolling feed. The current live snapshot (feed blob
`c84f360d2f4120615fcd5a442322e298b9c503bb`, state blob
`4d6f5fd872ecde881335263a69f23beb59504865`) is cycle 71355,
01:22:06 UTC, with 24 silent cycles, one rejected semantic echo and
four queued scheduler events. The public 160-entry feed includes the
unanswered Owen reading request at index 105; 157 character turns,
134 with an intention-style lexical marker, one question mark.
This is a **live observation**, not a same-snapshot model comparison.

**Hypothesis and prespecified negative controls:** when the rolling
conversation drops the witnessed request, the next native beat loses
the evidence. A source-ID-linked, public-only, explicitly addressed
pending record in the native checkpoint should retain it across restart
and feed eviction, without sharing it with other characters. Unknown
visibility, private unwitnessed messages, colliding IDs, unlinked
chatter, and private replies must not create false memories or closure.
Speech remains voluntary.

**Red test commit** `b545dcc6`, native CI
https://github.com/maaronfanberg-lab/me-/actions/runs/44215325041:
14 bridge tests yielded 1 failure and 1 error. The real scripted
native-engine second beat lacked Allen's original ID after the feed
was evicted; the helper was deliberately absent. **Green candidate**
`1167df91`, native CI
https://github.com/maaronfanberg-lab/me-/actions/runs/44215349858:
completed success; social-memory CI
https://github.com/maaronfanberg-lab/me-/actions/runs/44215349940:
completed success. Candidate only, no merge or production restart.

The change retains up to 24 unique public Allen source records in
`pending_social_evidence` in the existing checkpoint. It carries
unresolved directed evidence into the *actual native engine world_contexts*
per addressee on subsequent beats. It does not convert a claim into
referee-verified work. It drops records only on a publicly witnessed,
explicitly linked reply; no arbitrary intent, silence or unrelated
speech counts. The test simulates eviction and restart and checks the
real native engine's input, not a mocked reply generator.

**Unresolved:** no actual Llama-generated published Owen reply, no
verified reading action, no real-world relationship improvement, no
matched LLM replay, and no independently measured improvement over
production. Explicit reply_to metadata is not yet guaranteed by the
publication bridge, so some old requests may remain pending even if
answered conversationally; the retention cap is a safety bound, not
semantic resolution. This candidate must remain isolated. Next
distinct experiment must measure generated replies and verified
consequences, not add another lexical evaluator.
