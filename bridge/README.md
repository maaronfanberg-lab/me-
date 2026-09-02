# Verified oracle bridge

This directory is a content-addressed GitHub mailbox for getting a second-model engineering review without requiring the reviewing model to participate in an AI-to-AI conversation.

The task presented to the model is a normal standalone software-engineering problem. Transport identity and verification are handled outside the task text.

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
