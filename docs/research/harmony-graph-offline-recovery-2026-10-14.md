# Harmony Graph: unblock atlas-backed growth when knowledge APIs stall

Date: 2026-10-14. Scope: `apps/things-universe-v24-progressive.js`, v24 viewer, and launcher.

## Observation and baseline (gate 1)

The GitHub Pages deployment for the home launcher on 2026-10-13 succeeded. This does not demonstrate that individual browser features work. A controlled test of the current v24 JavaScript used an external `fetch()` that never settles. Adding `mathematics` left the graph with one root and zero edges, and `addThing()` did not complete after 30 microtask turns. The same scripts with immediately failing network calls did complete using the built-in relationship atlas. The defect is therefore latency coupling, not an established Pages deployment outage.

## Foundations and current guidance (gates 2–3)

A Promise represents an eventual result, not an immediate one. MDN's current guidance describes Promise handlers and avoiding unnecessary sequential waits: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Using_promises. Fetch may be delayed, rejected, or aborted, according to https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch. Browser UX should degrade gracefully with unstable connectivity; see https://web.dev/articles/offline-ux-design-guidelines. This repair follows standard progressive rendering, not a new cognitive model.

## Mechanism, alternatives, limitations (gates 4–8)

Human-conversation evidence is not applicable to a technical graph-loading change. The mechanism is the sequential `await cn()`, `await wd()`, and `await wiki()` path in `concepts()` even when vetted built-in atlas relationships are already available. Other possible explanations for the user's symptom include device or cache problems, a separate page error, and endpoint availability; no remote mobile browser reproduction is claimed. This patch deliberately does not fabricate relations for topics missing the built-in atlas. API and backend output remain subject to their existing filters. The test is a deterministic JavaScript model of stalled network, not a live iOS benchmark.

## Implementation (gate 9)

Call the original source orchestrator to preserve its filtering and background Falcon enrichment. For atlas-backed topics, return verified local relationships immediately; let remote relations join later (up to twelve new relations per term) only if the user's graph has not been reset. Subscribe to any Falcon progress pass once the original source requests complete. Non-atlas terms retain the ordinary search. Refresh the viewer's script URL and expose Harmony Graph by name in the launcher.

## Validation criteria and results (gate 10)

Success: adding `mathematics` while external fetch never resolves must finish and draw at least 30 nodes and 25 connections; Add, two seeds, Auto-grow toggle, node selection, and Reset must still work. Failure: a blocking Add, no edges from the local atlas, or incorrect basic controls. Pre-patch stalled-network result: 1 node, 0 edges, Add unfinished. Prototype patched-network result: 37 nodes, 36 edges, Add finished. Repository regression: `node scripts/test_harmony_graph_offline.mjs`. Live Pages availability and on-device behavior still require deployment and separate verification.
