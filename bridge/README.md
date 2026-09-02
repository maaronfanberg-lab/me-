# Verified oracle bridge

This directory is a content-addressed GitHub mailbox for getting a second-model engineering review without requiring the reviewing model to participate in an AI-to-AI conversation.

The task presented to the model is a normal standalone software-engineering problem. Transport identity and verification are handled outside the task text.

## How it works

1. Create `bridge/inbox/<request-id>.json`.
2. GitHub Actions runs `.github/workflows/claude-bridge.yml`.
3. `bridge/claude_bridge.py` canonicalizes and SHA-256 hashes the exact request.
4. If `ANTHROPIC_API_KEY` exists, the bridge uses Anthropic directly. Otherwise it tries the currently configured Claude candidates through GitHub Copilot CLI.
5. Copilot fallback answers are accepted only when OpenTelemetry identifies every resolved response model as Claude. Unverified or non-Claude responses are discarded.
6. The workflow writes `bridge/outbox/<request-id>.json` containing the request hash, nonce, transport, verified model family, resolved model, and response.
7. A consumer can recompute the request hash before trusting the answer.

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
  "max_tokens": 1800
}
```

Only `prompt` is required. If `nonce` is omitted, the bridge derives one from the request hash. `context`, `expected_response`, `model`, `copilot_models`, `max_tokens`, and `system` are optional.

## Neutral task boundary

The default prompt does not tell the reviewing model that another AI authored the task, does not ask it to converse with another model, and does not depend on an AI identity handshake. It simply asks for a read-only engineering review of the supplied material.

## Claude routing

The default Copilot candidate order is:

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

For Copilot fallback, the bridge additionally requires OpenTelemetry model evidence. A merely successful CLI exit code is not sufficient.

## Security boundary

The workflow sends only the request JSON content to the model provider. Secrets remain in GitHub Actions. Outbox files are committed to this public repository, so requests must not contain private or secret material.
