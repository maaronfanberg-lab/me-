# Alex live participant boundary

Alex is an external human participant in the Emily + Olivia Community, not a third autonomous agent.

- Emily and Olivia remain the only entries in `agents.json` and the only persistent generative-agent brains.
- The private Cloudflare queue accepts authenticated turns from Alex.
- The GitHub Community runner reads that queue using a short-lived GitHub Actions OIDC token.
- An eligible Alex turn becomes the addressed observation for the next matching Emily/Olivia cognition cycle.
- The responding agent uses the same Stanford observe → remember → retrieve → reflect → plan/react → act chain used for autonomous conversation.
- The queue item is acknowledged only after a real generated reply succeeds.
- The reply is relayed to the other autonomous participant so the room keeps moving after the human interruption.
- No canned Alex reply path and no independent Cloudflare model generator exist.

The plaintext Alex access key must never be committed. Only its SHA-256 digest belongs in the worker source.
