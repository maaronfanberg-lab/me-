# Verified oracle bridge

This directory is a content-addressed GitHub mailbox for getting a second-model engineering review without requiring the reviewing model to participate in an AI-to-AI conversation.

The task presented to the model is a normal standalone software-engineering problem. Transport identity and verification are handled outside the task text.

## Cross-chat quickstart

This section is intentionally explicit so a fresh ChatGPT conversation can discover and operate the bridge without relying on memory from another chat.

If the user asks to "use the Claude bridge", "consult Claude", or uses the standing `.` collaboration command, the assistant should use its connected GitHub tooling on repository `maaronfanberg-lab/me-` and perform this exact request/reply cycle.

### Preconditions

- The assistant must have GitHub read access to this repository and write access sufficient to create a file on `main`. If write access is unavailable, report that limitation instead of pretending the consultation occurred.
- Use a brand-new request id every time. Before sending, make sure the matching `bridge/outbox/<request-id>.json` does not already exist. Never reuse an id whose outbox already exists.
- Send exactly one new `bridge/inbox/*.json` request per commit/push. The push-trigger resolver intentionally selects one inbox request from the triggering commit, so bundling multiple new requests into one push is unsupported.

### Request/reply cycle

1. Pick a unique request id, for example `claude-consult-20260907-0915-topic`.
2. Create `bridge/inbox/<request-id>.json` on `main` with at least:

```json
{
  "prompt": "Review the current engineering question and give the likeliest cause, safest next operation, and falsification tests.",
  "context": ["Concise relevant repository context goes here."],
  "expected_response": "Concrete read-only engineering review with evidence from repository files when useful.",
  "claude_code_model": "sonnet",
  "claude_code_max_turns": 4
}
```

3. The push automatically triggers `.github/workflows/claude-bridge.yml`, workflow name `Verified oracle mailbox`.
4. Poll for the matching `bridge/outbox/<request-id>.json` on `main`. A normal assistant using GitHub file tools can simply retry that exact path every 10–20 seconds. The workflow has an 8-minute job timeout, so if no outbox appears within roughly 8 minutes, treat that as a transport failure and inspect the workflow run/logs when Actions-read tooling is available.
5. Read `bridge/outbox/<request-id>.json`.
6. Accept it as a Claude consultation only if it contains all of:
   - `protocol: "content-addressed-oracle-v1"`
   - `ok: true`
   - `verified_model_family: "claude"`
   - a non-empty `response`
   - request identity/hash fields corresponding to the inbox request
7. If the outbox is absent after the wait budget or reports an error, diagnose the bridge. Never invent or paraphrase a Claude response that did not arrive.
8. Independently evaluate Claude's recommendation. Claude is advisory and read-only.

`workflow_dispatch` is an optional alternate trigger for an inbox request that already exists. It is not required for normal ChatGPT operation and should not replace the one-request-per-push path above unless the caller specifically needs to rerun an existing request and has Actions-dispatch tooling.

Standing collaboration shorthand used by the project:

- `.` = consult Claude through this bridge.
- `.+` = consult Claude, independently evaluate the advice, then implement only the portions judged sound, safe, and authorized.

The bridge is discrete request/reply. It is not a persistent Sarah↔Claude chat, and the Claude Code transport is invoked with no session persistence.

## How it works

1. Create `bridge/inbox/<request-id>.json`.
2. GitHub Actions runs `.github/workflows/claude-bridge.yml`.
3. The request is canonicalized and SHA-256 hashed before the response is trusted.
4. If `CLAUDE_CODE_OAUTH_TOKEN` exists, the workflow uses the official Claude Code CLI against the user's existing Claude subscription through `bridge/claude_code_oracle.py`.
5. Subscription-mode Claude is restricted to `Read`, `Glob`, and `Grep`. It cannot run shell commands, edit/write files, create commits, or dispatch workflows.
6. Claude Code answers are accepted only when its JSON `modelUsage` identifies the resolved response models as Claude.
7. If no subscription token exists, the bridge retains the GitHub Copilot fallback in `bridge/claude_bridge.py`; Copilot answers are accepted only when OpenTelemetry identifies every resolved response model as Claude.
8. The workflow deliberately withholds `ANTHROPIC_API_KEY`, so it cannot silently fall back to separately billed Anthropic API usage.
9. The workflow writes `bridge/outbox/<request-id>.json` containing the request hash, nonce, transport, verified model family, resolved model, and response.
10. A consumer can recompute the request hash before trusting the answer.

## Request format

```json
{
  "nonce": "emily-olivia-social-loop-001",
  "prompt": "Review this bounded retry design and identify any liveness failure.",
  "context": [
    "The outer social refractory guard permits one retry.",
    "All inner boundary and session retry multipliers are one-pass."
  ],
  "expected_response": "Give the likely failure mode, safest change, and falsification tests.",
  "claude_code_model": "sonnet",
  "claude_code_max_turns": 4
}
```

Only `prompt` is required. If `nonce` is omitted, the bridge derives one from the request hash. `context`, `expected_response`, `claude_code_model`, `claude_code_max_turns`, `copilot_models`, `max_tokens`, and `system` are optional.

## Secondary Claude access through a personal Copilot entitlement

The workflow first attempts the Claude Code subscription. If the result reports an explicit subscription usage-limit error, it now tries Claude using the GitHub Copilot CLI. It rejects Copilot responses unless telemetry verifies the resolved model belongs to Claude. This is an authorized second provider route, **not** a subscription-quota bypass.

**Important for personal repositories:** GitHub Actions' automatically supplied `GITHUB_TOKEN` is an installation token, not a user's Copilot entitlement. Our initial test on 2026-11-10 showed all three requested Claude models were unavailable to that installation token. According to GitHub's first-party documentation, a user-owned fine-grained personal access token (PAT) with **Account → Copilot Requests** may instead use that person's Copilot plan and model availability. Eligibility and quota remain dependent on the user's account.

To enable:

1. Verify you can select a Claude model in the GitHub Copilot UI or Copilot CLI under your own account.
2. Generate a **fine-grained personal access token** at https://github.com/settings/personal-access-tokens/new . Set **Resource owner** to your *personal account*; set **Account permissions → Copilot Requests** to the required permission. Grant only the necessary repository access and set an expiration.
3. In repository `maaronfanberg-lab/me-`, go to Settings → Secrets and variables → Actions → New repository secret. Name the secret **`COPILOT_GITHUB_TOKEN`** and paste the token only into the GitHub secret field.
4. Submit one fresh `bridge/inbox/<id>.json` smoke test. Do not reuse old failed request ids. Check the matching outbox for `ok: true`, `verified_model_family: "claude"`, and `transport: "github-copilot-claude-verified-by-otel"`.

Never place the PAT in GitHub source files, JSON mailbox messages, issues, or this chat. The workflow scopes the token to the oracle execution step and withholds it from the Claude Code subscription subprocess. A personal Copilot token has separate usage and billing terms; review GitHub pricing and any premium-request charge before enabling.

Docs: https://docs.github.com/en/copilot/concepts/agent-capabilities/agent-powered-workflows-and-operations/copilot-cli-in-github-actions and https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/authenticate-copilot-cli .

## Human-guided multi-turn relay

The bridge is currently discrete request/reply rather than an endless bot-to-bot chat. ChatGPT can cite the previous outbox and explicitly include a bounded prior-turn summary in the `context` of a fresh inbox request. The next Claude answer is stored in a fresh outbox record. This provides a practical, human-controlled multi-turn conversation with verification, no shared subscription-session requirement, and no automatic recursive workflow triggers. The public inbox/outbox are unsuitable for sensitive conversations.

## Claude subscription authentication

Generate the long-lived subscription OAuth credential with Claude Code:

```bash
claude setup-token
```

Store the resulting value as the GitHub Actions repository secret `CLAUDE_CODE_OAUTH_TOKEN`. Do not commit it, place it in an inbox request, or paste it into a chat.

When that secret exists, the workflow installs Claude Code and uses the subscription transport automatically. The transport removes `ANTHROPIC_API_KEY` and `ANTHROPIC_AUTH_TOKEN` from the child process before invoking Claude so an API credential cannot take precedence over the subscription token.

## Neutral task boundary

The default prompt does not tell the reviewing model that another AI authored the task, does not ask it to converse with another model, and does not depend on an AI identity handshake. It simply asks for a read-only engineering review. Claude may inspect repository files using only the explicitly allowed read-only tools.

## Copilot fallback routing

When no Claude subscription token is configured, the default Copilot candidate order is:

1. `claude-sonnet-5`
2. `claude-opus-5`
3. `claude-haiku-4.5`

The list can be overridden per request with `copilot_models` or by setting `COPILOT_CLAUDE_MODELS` as a comma-separated workflow environment variable. This allows model availability to change without changing the protocol.

## Verification boundary

A successful outbox record must contain:

- `protocol: content-addressed-oracle-v1`
- `ok: true`
- the exact `request_sha256`
- the matching `request_nonce`
- `verified_model_family: claude`
- a non-empty `response`

For the Claude Code subscription transport, the bridge requires Claude Code's own JSON `modelUsage` evidence and rejects results marked `is_error`. For Copilot fallback, the bridge requires OpenTelemetry model evidence. A merely successful CLI exit code is not sufficient for either transport.

## Security boundary

Secrets remain in GitHub Actions and are never written to the public outbox. Outbox files are committed to this public repository, so requests and model responses must not contain private or secret material.
