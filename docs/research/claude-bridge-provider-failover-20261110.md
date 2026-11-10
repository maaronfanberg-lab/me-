# Claude bridge provider failover: bounded engineering change (2026-11-10)

## Observed problem and research question
A GitHub mailbox request `bridge/inbox/relay-conversation-architecture-20261110-a1.json` successfully triggered the existing oracle workflow, but the outbox returned `ok: false`, `Claude Code exited 1`, with `You've hit your 5-hour limit`. The workflow only invokes the Copilot Claude adapter when `CLAUDE_CODE_OAUTH_TOKEN` is absent. Thus a configured but exhausted subscription blocks the already-implemented independent Copilot route.

Question: Can a specific subscription quota failure trigger one independently verified Copilot Claude attempt without masking other errors, charging Anthropic API credits unexpectedly, or creating an autonomous workflow loop?

## 10-level research gate (technical applicability)
1. **Observation:** GitHub inbox -> workflow -> outbox works; subscription transport returned a recorded quota error, not a Claude response. Baseline: `ok: false`.
2. **Foundation:** Event-driven request/reply, bounded retries, fail-closed response verification, and independent authorization are established distributed-systems patterns.
3. **Current first-party documentation:** Anthropic confirms Claude and Claude Code subscription allowances are shared: https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-max-or-ultra-plan . GitHub confirms Copilot CLI supports noninteractive `-p`, explicit `--model`, and JSONL output: https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference . GitHub warns ordinary workflow `GITHUB_TOKEN` pushes do not retrigger most workflows: https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow .
4. **Natural-behavior evidence:** Not applicable: this change is transport routing, not modeled human conversation.
5. **Mechanism:** A script detecting verified subscription-quota error text can try a separately entitled GitHub Copilot CLI invocation. Existing adapter accepts replies only with Claude model telemetry.
6. **Competing paths:** Anthropic API requires separately billed key; the official `@claude` GitHub Action typically uses Anthropic credentials; a second hop using the same subscription quota cannot help.
7. **Limits:** Copilot entitlement, model availability, AI credit limits, CLI behavior, and provider pricing may prevent fallback. No guaranteed response; no bypass of Anthropic quota. Do not treat the fallback as successful without a verified outbox.
8. **Context transfer:** Existing public repo is suitable only for non-sensitive requests. Each inbox request is one workflow trigger. No autonomous chains added.
9. **Implementation:** Keep existing inbox/outbox protocol; in `.github/workflows/claude-bridge.yml`, when subscription mode fails with an explicit quota marker, install and run existing Copilot adapter; otherwise preserve the original failure. Strip Anthropic API credentials. Use the existing `copilot-requests: write` permission and model-verification logic.
10. **Validation:** Submit exactly one new small inbox request. Require matching identity, `protocol`, `ok: true`, `verified_model_family: claude`, nonempty `response`, and `transport: github-copilot-claude-verified-by-otel`; otherwise report the actual failure and do not claim Claude answered. No automatic recursive calls. A fake-authentication or non-quota failure must not trigger fallback.

## Post-change validation
Pending deployment and live test. Any outcome other than a verified Claude response is a transport failure, not evidence of a working secondary provider.
