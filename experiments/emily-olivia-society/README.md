# Emily + Olivia Society

An isolated two-agent social simulation experiment inspired by AgentSociety 2.

This experiment is deliberately separate from The Room and from the BitNet experiment.

## Agents

- Emily, age 27
- Olivia, age 29

No personality traits, relationship history, goals, jobs, location, or backstory are assumed yet.

## Architecture

Each agent will have her own workspace and memory. A small social environment will mediate what each agent can observe and what messages/actions she can send. A coordinator advances the simulation one step at a time and records replayable events.

Planned local structure:

- `agents.json` — immutable starting profile data
- `run.py` — two-agent AgentSociety 2 launcher
- `workspaces/emily/` — Emily's private workspace and memory
- `workspaces/olivia/` — Olivia's private workspace and memory
- `replay/` — append-only interaction trace

## Isolation rule

Nothing in this experiment imports, writes to, launches, or configures The Room. Nothing in this experiment uses the BitNet branch.
