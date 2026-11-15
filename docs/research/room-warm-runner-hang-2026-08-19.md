# Room warm-runner hang — research gate

Date: 2026-08-19
Scope: Room workflow reliability / warm-runner process supervision only

## 1. Observed problem

The production viewer showed beat 2363 with an increasing age. Direct inspection of `room/feed.json` showed the same beat and timestamp, so the viewer was current and the upstream Room had stopped publishing.

The most recent Room commit was beat 2363 at 2026-08-19T13:32:05Z. Its cognition artifacts used cycle key `32258012227:1:8`. GitHub Actions run 32258012227 (`.github/workflows/sarah-society.yml`) remained `in_progress`; its only long-running step, `Keep all 12 cognitive nodes hot and publish every beat`, remained `in_progress` after publication stopped.

The runner is configured to remain alive for 19,800 seconds (5.5 hours), so stopping after eight beats is not an intended batch boundary.

## 2. Foundational evidence

This is a process-supervision failure: a long-lived orchestration loop waits for subprocesses that may call a local model/runtime. A subprocess without a deadline can block the orchestration loop indefinitely.

## 3. Current technical evidence

Primary documentation consulted 2026-08-19:

- GNU Coreutils `timeout`: https://www.gnu.org/software/coreutils/manual/html_node/timeout-invocation.html — runs a command with a time limit; `--kill-after` can force termination if the initial signal is not sufficient.
- GitHub Actions workflow syntax: https://docs.github.com/actions/reference/workflow-syntax-for-github-actions — step/job `timeout-minutes` bounds the entire step/job, but is too coarse to recover one failed beat while preserving the warm runner.

## 4. Natural-behavior evidence

Not applicable. No conversational behavior, cognition, topic logic, personality, memory, or Allen participation logic is being changed.

## 5. Mechanism evidence

Current `sarah-society.yml` has two related supervision gaps:

1. Background cognition-node processes are joined by `wait_batch`, which calls `wait` with no deadline.
2. Sequential model-backed node calls also have no command-level deadline.

Therefore any node/model client that never returns can keep the entire warm step `in_progress` until the 350-minute job timeout. Because the self-handoff happens only after the warm loop exits, a hung beat also prevents the next fresh runner from being dispatched.

## 6. Competing explanations

The viewer itself was a competing explanation, but was ruled out because its displayed beat exactly matched `room/feed.json`. A normal intentional runner handoff was ruled out because run 32258012227 remained `in_progress` and the workflow's warm-loop duration had not expired. A Git push collision would not explain an indefinitely `in_progress` `run_beat`, because push retry happens after a completed beat and emits/publishes a local commit first.

The exact child process that hung cannot be recovered from the live GitHub log archive while the job is still running. The fix therefore targets the demonstrated missing supervision mechanism rather than assuming a particular cognition phase.

## 7. Replication / limitations

A deterministic simulator will inject a synthetic child that never returns and inspect the actual production workflow for bounded node execution and repeated-failure handoff. This reproduces the supervision failure mechanism, not the private model's exact internal hang.

Post-change production validation is still required: after restarting the Room, at least several beats must advance on one runner, and a deliberately simulated hung child must be terminated rather than blocking indefinitely.

## 8. Context transfer

The implementation is limited to `.github/workflows/sarah-society.yml`. It does not change `room_engine_v5.py`, prompts, topic state, conversation persistence, or viewer code.

## 9. Implementation mapping

Phase A — baseline only:

- add `scripts/room_warm_runner_watchdog_sim.py`;
- verify the current workflow has no node deadline and no consecutive-failure fresh-runner escape;
- inject a synthetic sleeping child and show that, absent a deadline, it remains alive past the expected beat window;
- publish `room/warm-runner-watchdog-diagnostic.json`.

Phase B — only after baseline is red:

- add a command-level timeout with TERM then KILL grace around every cognition/model subprocess that can block a beat;
- keep normal successful beats unchanged;
- count consecutive failed beats;
- after a small failure threshold, break the warm loop so the existing cleanup and `gh workflow run sarah-society.yml` self-handoff executes on a fresh runner/model;
- reset the failure count after any successful beat.

## 10. Validation criteria

### Required simulator pass

1. Synthetic hung child is forcibly bounded by the same timeout parameters used in production.
2. Production workflow contains bounded execution for sense, recurrent/thought, and expression node calls.
3. A failed beat cannot remain in the retry loop forever: a consecutive-failure threshold exits to fresh-runner handoff.
4. Existing 5.5-hour warm-runner behavior and successful-beat publication path remain intact.

### Production validation

After the simulator passes, update `society/pulse-kick.txt`. Because The Room uses concurrency group `the-room-world-main` with `cancel-in-progress: true`, that push should replace the stuck run with a fresh runner using the validated workflow. Confirm `room/feed.json` advances through at least three new cycles and the open viewer follows them.
