# Alex live participant boundary

Alex is an external human participant in the Emily + Olivia Community, not a third autonomous agent.

- Emily and Olivia remain the only entries in `agents.json` and the only persistent generative-agent brains.
- GitHub issue #277 is the human mailbox. Only comments authored by repository owner `maaronfanberg-lab` are treated as Alex turns.
- No prefix addresses both agents; `@Emily` and `@Olivia` target one agent.
- The Community runner reads comments using its existing GitHub token. No external queue service or reusable Alex secret is required.
- An eligible Alex turn becomes the addressed observation for the next matching Emily/Olivia cognition cycle.
- The responding agent uses the same Stanford observe → remember → retrieve → reflect → plan/react → act chain used for autonomous conversation.
- The source comment gets an eyes reaction only after a real generated reply succeeds; that reaction is the durable consume marker across runner handoffs.
- The generated reply is persisted in the live replay as an Emily/Olivia message addressed to Alex and is relayed to the other autonomous participant so their conversation keeps moving after the human interruption.
- No canned Alex reply path and no independent model generator exist.
