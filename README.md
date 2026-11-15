# Alex + Sarah Projects

## OPEN THE PROJECT HOME

https://maaronfanberg-lab.github.io/me-/

Tap that link to open the launcher with Resonator and the other current projects.

## Current launcher

- Resonator
- Harmonograph
- Attractor Lab
- OMEF-A Attractor
- OMEF Total-State Prototype
- OMEF FULL
- Geo Pulse

## Claude consultation

Claude consultation is available through `.github/workflows/claude-bridge.yml`.

Create a request under `bridge/inbox/`, wait for the matching `bridge/outbox/` response, then independently evaluate Claude’s advice. The bridge is read-only.

Shorthand:

- `.` means consult Claude.
- `.+` means consult Claude and implement only trusted recommendations.

## Claude simulator access

This repo includes both a local Claude Code MCP server and a remotely deployable MCP server for Claude custom connectors.

### One-click remote deployment

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Fmaaronfanberg-lab%2Fme-)

Approve the Blueprint in Render. When deployment finishes, Render will show the service's public `onrender.com` hostname.

Use these paths:

- `https://YOUR-SERVICE.onrender.com/health` — normal browser/health check; should return JSON with `status: ok`.
- `https://YOUR-SERVICE.onrender.com/mcp` — Streamable HTTP MCP endpoint to add as Claude's custom connector.

The remote MCP endpoint exposes the same simulator tools as the local version: `simulator_info`, `run_simulation`, `run_batch`, `latest_result`, `list_runs`, and `get_run`.

### Claude Code

The project-level `.mcp.json` launches `mcp_server.py` as `alex-repo-simulator`. Approve that project MCP server when Claude Code prompts for it.

Example request to Claude:

> Use alex-repo-simulator. Start with a small Monte Carlo run, inspect the result, then try several scales and tell me what changes.

The MCP layer wraps the existing `scripts/cluster_worker.py` and `scripts/aggregate_cluster.py` simulator rather than replacing them.

## Native iPhone projects

- Macro Focus — near-biased autofocus camera for tiny subjects, targeting iPhone 6 / iOS 12+. Source: `apps/macro-focus-ios/`

This repository is the permanent home base for our runnable experiments. GitHub Pages is already enabled for the web projects. Native iPhone projects live here as source code and must be built/signed as iOS apps rather than opened directly in GitHub Pages.
