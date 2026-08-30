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

## Build and runtime policy

Cloudflare is not used to build or run this experiment.

- GitHub stores the code.
- GitHub Actions is manual-only and used for explicit foundation checks.
- `runtime.sh` is the host-neutral launcher for a normal Linux machine or VPS.
- `Dockerfile` packages the same runtime for any Docker-capable host.
- Cloudflare may later be used only as an optional thin proxy/front door. It must not own the Python build.

Local or VPS setup:

```bash
cd experiments/emily-olivia-society
bash runtime.sh
```

Docker setup:

```bash
docker build -t emily-olivia-society .
docker run --rm emily-olivia-society
```

Both launch paths currently initialize the two-agent society and exit before autonomous interaction.

## Layers

### Layer 1 — Foundation — COMPLETE

- exactly two agents
- pinned upstream research code
- reproducible bootstrap
- generated state excluded from git
- no autonomous interaction
- no Room or BitNet imports

### Layer 2 — Individual cognition — COMPLETE

Use Stanford's actual `GenerativeAgent`, memory stream, persistence format, `remember`, and `reflect` machinery. Emily and Olivia have separate private Stanford-format workspaces.

### Layer 3 — Social environment — COMPLETE

The social layer now uses AgentSociety 2's `EnvBase`, `@tool`, and `CodeGenRouter` machinery through `controlled_social_space.py`.

The boundary is private by default:

- `observe_social_space(agent_id)` is read-only.
- An agent can see participant names and only messages addressed to her.
- `send_message(agent_id, recipient_id, content)` is the only social mutation.
- Self-messaging is rejected.
- Unknown agent IDs are rejected.
- Empty messages are rejected.
- Stanford cognition workspaces and memory files are never exposed through the social environment.
- Advancing environment time does not automatically generate speech or actions.

No autonomous interaction is enabled yet.

### Layer 4 — Coordinator

Use AgentSociety 2's society/coordinator execution model to advance one explicit step at a time and record a replayable trace.

### Layer 5 — Interaction

Allow a first bounded Emily ↔ Olivia exchange. No indefinite autonomous loop yet.

### Layer 6 — Persistence and reflection

Persist each agent's private memory separately, then verify later turns retrieve prior experiences and reflections rather than relying only on prompt history.

### Layer 7 — Observation

Add a simple read-only viewer for events, memories, and state. Observation must not silently mutate the simulation.

## Current launcher

`run.py` uses AgentSociety 2's `AgentSociety`, `CodeGenRouter`, and the controlled `EnvBase` social module to initialize the two-agent environment. It intentionally stops before autonomous interaction.

## Isolation rule

Nothing in this experiment imports, writes to, launches, or configures The Room. Nothing in this experiment uses BitNet. The Room remains outside this experiment unless that boundary is explicitly changed later.
