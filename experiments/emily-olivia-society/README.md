# Emily + Olivia Community

An isolated two-agent community experiment built from research code rather than a home-grown agent framework.

This experiment is deliberately separate from The Room and from the BitNet experiment.

## Agents

- Emily, age 27
- Olivia, age 29

No personality traits, relationship history, goals, jobs, location, or backstory are assumed yet.

## Research-code rule

Use upstream code first. Write local code only where an adapter is genuinely required.

- **Community runtime:** Tsinghua AgentSociety 2 (`agentsociety2==2.8.4`). The upstream Python class remains named `AgentSociety`; locally we call the project a community.
- **Individual cognition/memory:** Stanford HCI `genagents`, pinned to commit `96854071ef4c2d79c93144c973c7820722d52bab`.
- Exact upstream pins live in `upstreams.json`.
- `bootstrap_upstreams.sh` installs AgentSociety 2 and checks out the pinned Stanford source without copying either project into this repository.

## Build and runtime policy

Cloudflare is not used to build or run this experiment.

- GitHub stores the code.
- GitHub Actions is manual-only and used for explicit foundation checks.
- `runtime.sh` is the host-neutral launcher for a normal Linux machine or VPS.
- `Dockerfile` packages the same runtime for any Docker-capable host.
- Cloudflare may later be used only as an optional thin proxy/front door. It must not own the Python build.

## Layers

### Layer 1 — Foundation — COMPLETE

- exactly two agents
- pinned upstream research code
- reproducible bootstrap
- generated state excluded from git
- no autonomous interaction
- no Room or BitNet imports

### Layer 2 — Individual cognition — COMPLETE

Stanford's actual `GenerativeAgent`, memory stream, persistence format, `remember`, `reflect`, retrieval, and interaction methods back each private workspace.

### Layer 3 — Social environment — COMPLETE

The shared layer uses AgentSociety 2's `EnvBase`, `@tool`, and `CodeGenRouter` machinery through `controlled_social_space.py`.

- `observe_social_space(agent_id)` is read-only.
- An agent sees participant names and only messages addressed to her.
- `send_message(agent_id, recipient_id, content)` is the only social mutation.
- Private Stanford cognition workspaces are never exposed through the shared environment.

### Layer 4 — Research-style agent cycle — COMPLETE

`community_cycle.py` implements one bounded cycle per agent:

1. observe the controlled shared environment
2. remember the observation with Stanford's memory stream
3. retrieve relevant prior memories with Stanford retrieval
4. choose a social action using Stanford's interaction/utterance code
5. optionally send one addressed message through the AgentSociety-derived environment
6. persist private memory back to that agent's Stanford workspace

The cycle is explicit and bounded. It will not run at startup. It requires:

```bash
.venv-stanford/bin/python community_cycle.py --one-cycle
```

If an agent has no new addressed message, the current Layer 4 behavior is `wait`; it does not invent a conversation opener. There is no indefinite autonomous loop.

### Layer 5 — First bounded interaction

Seed one explicit event or addressed message and allow the research-style cycle to produce the first Emily ↔ Olivia exchange. Still no indefinite loop.

### Layer 6 — Persistence and reflection

Verify later cycles retrieve prior experiences and use Stanford reflection rather than relying only on current prompt context.

### Layer 7 — Observation

Add a read-only viewer for events, memories, and state. Observation must not silently mutate the community.

## Current launchers

`run.py` initializes the Emily + Olivia Community and controlled environment, then exits without autonomous interaction.

`community_cycle.py --one-cycle` is the only path that permits one explicit observe → remember → retrieve → choose → act cycle per agent.

## Isolation rule

Nothing in this experiment imports, writes to, launches, or configures The Room. Nothing in this experiment uses BitNet. The Room remains outside this experiment unless that boundary is explicitly changed later.
