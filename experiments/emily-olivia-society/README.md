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
- `send_message(agent_id, recipient_id, content)` is the social send operation.
- `consume_message(agent_id, message_id)` removes a message after that recipient processes it, preventing duplicate replies on later cycles.
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

### Layer 5 — First bounded interaction — COMPLETE

`first_exchange.py` permits exactly one bounded exchange:

1. one explicit opener from Emily to Olivia
2. Olivia observes, remembers, retrieves, chooses, and may reply
3. Emily observes Olivia's reply, remembers, retrieves, chooses, and may reply
4. processed messages are consumed
5. both private workspaces are persisted
6. a replay is written to `replay/first_exchange.json`
7. execution stops

It will not start unless explicitly permitted:

```bash
.venv-stanford/bin/python first_exchange.py --run
```

The default neutral opener is `Hello, Olivia.` and can be replaced with `--opener`.

There is still no indefinite autonomous loop.

### Layer 6 — Persistence and reflection — COMPLETE

`persistence_reflection.py` verifies that cognition survives beyond the current exchange instead of relying on prompt history alone.

For each agent it:

1. reloads the private Stanford workspace
2. retrieves memories relevant to the other agent
3. runs Stanford's real `MemoryStream.reflect(...)` with explicit named arguments
4. adds generated reflection nodes to the same private memory stream
5. saves the workspace
6. reloads it through Stanford's `GenerativeAgent` loader
7. verifies the reflection nodes survived the process boundary
8. retrieves relevant memories again after reload
9. writes the bounded verification report to `replay/layer6_reflection.json`
10. stops

Layer 6 is explicit and will not run automatically:

```bash
.venv-stanford/bin/python persistence_reflection.py --run
```

If an agent has no prior memories yet, reflection is skipped rather than invented.

Implementation note: Stanford's current `GenerativeAgent.reflect(anchor, time_step)` forwards its second positional argument into the lower-level `reflection_count` slot. Layer 6 therefore calls Stanford's actual `MemoryStream.reflect(...)` directly with named `reflection_count`, `retrieval_count`, and `time_step` arguments. No reflection algorithm is reimplemented locally.

### Layer 7 — Read-only observation — COMPLETE

`observer.py` inspects persisted community state without importing or invoking either research runtime.

It reads only:

- `workspaces/emily/scratch.json`
- `workspaces/emily/memory_stream/nodes.json`
- Emily's embeddings/meta files for integrity hashes
- the equivalent Olivia files
- JSON replay files under `replay/`

The observer never calls `remember`, `reflect`, retrieval, `utterance`, `send_message`, `consume_message`, or an environment step. It computes SHA-256 hashes before and after observation and aborts if persisted state changes while being observed.

Full read-only view:

```bash
python3 observer.py
```

Compact status view:

```bash
python3 observer.py --summary
```

No model/API key is needed merely to observe persisted state.

## Current launchers

`run.py` initializes the Emily + Olivia Community and controlled environment, then exits without autonomous interaction.

`community_cycle.py --one-cycle` permits one explicit observe → remember → retrieve → choose → act cycle per agent.

`first_exchange.py --run` permits exactly the first bounded Emily ↔ Olivia exchange and then exits.

`persistence_reflection.py --run` permits exactly one persistence/reflection verification pass for Emily and Olivia, then exits.

`observer.py` is read-only and can inspect persisted state without starting cognition or interaction.

## Isolation rule

Nothing in this experiment imports, writes to, launches, or configures The Room. Nothing in this experiment uses BitNet. The Room remains outside this experiment unless that boundary is explicitly changed later.
