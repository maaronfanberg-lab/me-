# Live Earth Oracle validation hardening — 2026-08-28

## Observed problem
The generic `Validate project apps` workflow could report success while only checking that repository `index.html` exists. It did not parse the Live Earth Oracle JavaScript or confirm that the nine intended feeds and core resilience guards remained present. A syntax error or accidental removal of a feed/failure guard could therefore merge and deploy without CI noticing.

## Research question
What is the smallest repository-local validation change that materially reduces silent-breakage risk without coupling the Oracle to the production Room or creating a broad fragile test suite for unrelated applications?

## Evidence and mechanism
- The existing workflow contained only `test -f index.html`, so its success did not validate the Oracle artifact.
- The Oracle is a standalone HTML file with inline JavaScript. Node's built-in `vm.Script` can parse classic inline JavaScript without adding third-party dependencies.
- Static checks can cheaply verify the presence of the nine configured streams, the satire disclaimer, expected source endpoints, timeout/stale/error machinery, WebSocket reconnect logic, visibility handling, and `Promise.allSettled` isolation.
- Pull-request execution catches breakage before merge; the existing push execution remains as a post-merge check.

## Competing explanations and limits
- Static parsing cannot prove that remote APIs are available, retain CORS access, or preserve response schemas.
- Presence checks cannot prove behavioral correctness; they prevent accidental deletion of important architecture, not subtle logic bugs.
- Full browser automation would provide stronger runtime coverage but would add more moving infrastructure and is not necessary to remove the immediate false-positive CI blocker.

## 10-level gate
1. Observed problem: passed from the workflow contents.
2. Foundational evidence: standard fail-fast CI and syntax validation; no novel behavioral theory involved.
3. Current evidence: current repository workflow and current Oracle implementation inspected directly.
4. Natural-behavior evidence: not applicable.
5. Mechanism evidence: direct mapping from missing validation to parse/presence checks.
6. Competing explanations: documented above.
7. Replication/limitations: static checks explicitly limited to deploy-time structural regressions.
8. Context transfer: isolated to the Oracle and its validator; unrelated Room behavior is untouched.
9. Implementation mapping: one dependency-free Node validator plus one workflow step and PR trigger.
10. Post-change validation: PR must run the validator successfully before merge; post-merge push must also pass.

## Validation criteria
- `node scripts/validate_live_earth_oracle.mjs` exits 0 on the current Oracle.
- A JavaScript syntax error causes a non-zero exit.
- Removal of any expected stream, key source endpoint, or core reliability guard causes a non-zero exit.
- The workflow runs on Oracle/validator/workflow pull-request changes and on pushes to `main`.
- No production Room code or state is modified.
