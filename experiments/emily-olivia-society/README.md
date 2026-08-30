# Emily + Olivia Society

An isolated two-agent social simulation experiment built from research code rather than a home-grown agent framework.

This experiment is deliberately separate from The Room and from the BitNet experiment.

## Agents

- Emily, age 27
- Olivia, age 29

No personality traits, relationship history, goals, jobs, location, or backstory are assumed yet.

## Research-code rule

Use upstream code first. Write local code only where an adapter is genuinely required.

- **Society/runtime:** Tsinghua AgentSociety 2 (`agentsociety2==2.8.4`)
- **Individual cognition/memory:** Stanford HCI `genagents`, pinned to commit `96854071ef4c2d79c93144c973c7820722d52bab`
- Exact upstream pins live in `upstreams.json`.
- `bootstrap_upstreams.sh` installs AgentSociety 2 and checks out the pinned Stanford source without copying either project into this repository.

## Layers

### Layer 1 — Foundation — COMPLETE

- exactly two agents
- pinned upstream research code
- reproducible bootstrap
- generated state excluded from git
- no autonomous interaction
- no Room or BitNet imports

### Layer 2 — Individual cognition

Use Stanford's actual `GenerativeAgent`, memory stream, `remember`, `reflect`, and persistence behavior. Add only the minimum settings/config adapter Stanford's repository requires.

### Layer 3 — Social environment

Use AgentSociety 2's `SimpleSocialSpace` and environment/router machinery so Emily and Olivia can observe and address each other through a controlled shared environment.

### Layer 4 — Coordinator

Use AgentSociety 2's society/coordinator execution model to advance one explicit step at a time and record a replayable trace.

### Layer 5 — Interaction

Allow a first bounded Emily ↔ Olivia exchange. No indefinite autonomous loop yet.

### Layer 6 — Persistence and reflection

Persist each agent's private memory separately, then verify later turns retrieve prior experiences and reflections rather than relying only on prompt history.

### Layer 7 — Observation

Add a simple read-only viewer for events, memories, and state. Observation must not silently mutate the simulation.

## Current launcher

`run.py` already uses AgentSociety 2's `AgentSociety`, `CodeGenRouter`, and `SimpleSocialSpace` to initialize the two-agent environment. It intentionally stops before autonomous interaction.

## Isolation rule

Nothing in this experiment imports, writes to, launches, or configures The Room. Nothing in this experiment uses BitNet. The Room remains outside this experiment unless that boundary is explicitly changed later.
