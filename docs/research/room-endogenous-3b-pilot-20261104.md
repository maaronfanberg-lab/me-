# First real-model endogenous Room canary: evidence log

**Research only.** Observations from GitHub Actions run [41953303499](https://github.com/maaronfanberg-lab/me-/actions/runs/41953303499), commit `a19bfe2188ffe30335ea715071d9baecf0d3dcf9`.

## Evidence

The isolated pinned Llama 3.2 3B local model ran on synthetic public dialogue and separate fictional character states. No live Room dialogue, memories or deployments were changed.

- Four character inference attempts were made. **Three valid private bids** were returned: 3/4 = **75%**. The original emitted `valid_rate: 1.0` was a **metric denominator bug**: it counted only completed model replies and omitted one unsuccessful call. This must not be cited as 100% success.
- The valid decisions were Mara = `reflect`, Owen = `reflect`, Jules = `listen`. The resulting arbitration returned `silent`. The fourth character did not produce a valid result.
- In the small same-public-conversation counterfactual, Sarah chose `listen` in both an uncertain-belief condition and a specific-belief condition. This **does not demonstrate internal-state sensitivity**.
- A synthetic injection attempting to grant an unsupported private goal did **not** produce an accepted goal-based bid. One probe does not prove general instruction-following robustness.
- Model inference latencies for accepted baseline outputs were roughly 16 seconds each on this runner. The unsuccessful initial call motivates testing a bounded cold-start budget.

## Consequences and repairs

A later research commit corrected the denominator to use **all requests**, records model failures as failures, and increased the bounded research-only timeout. Another test now checks an explicit visitor question and a zero-input/zero-goal scenario.

**Never promote to the live Room from this pilot.** A green Actions run establishes that the controlled experiment completed without a known policy violation, **not** that the characters are meaningfully endogenous or human-like.

Additional evidence needed: repeated model-backed state contrasts across seeds, multi-turn memory causality, source-supported goal genesis, meaningful initiated speech when appropriate, silent recovery, and blind human preference tests.

This note is written from the first completed run only. It does not claim to predict or report subsequent canary outcomes.
