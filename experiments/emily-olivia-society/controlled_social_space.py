from __future__ import annotations

from datetime import datetime

from agentsociety2.env import EnvBase, tool


class ControlledSocialSpace(EnvBase):
    """Two-agent social boundary built with AgentSociety 2 environment tools.

    This layer deliberately exposes only names and addressed message queues.
    It never reads either agent's private Stanford workspace or memory files.
    """

    def __init__(self, agent_id_name_pairs: list[tuple[int, str]]):
        super().__init__()
        if len(agent_id_name_pairs) != 2:
            raise ValueError("ControlledSocialSpace requires exactly two agents.")

        self._names = {int(agent_id): str(name) for agent_id, name in agent_id_name_pairs}
        if len(self._names) != 2:
            raise ValueError("Agent IDs must be unique.")

        self._inboxes: dict[int, list[dict]] = {agent_id: [] for agent_id in self._names}
        self._next_message_id = 1
        self.t: datetime | None = None

    @classmethod
    def description(cls) -> str:
        return "A private-by-default two-agent social space with addressed messaging."

    @classmethod
    def init_description(cls) -> str:
        return """ControlledSocialSpace

A two-agent social environment built with AgentSociety 2 EnvBase and @tool.

Available tools:
- observe_social_space(agent_id): read-only; returns participant names and that agent's addressed inbox.
- send_message(agent_id, recipient_id, content): mutating; sends one explicit message to the other registered participant.
- consume_message(agent_id, message_id): mutating; removes one addressed message after it has been processed.

Private cognition workspaces and memory files are not exposed by this environment.
"""

    def _require_agent(self, agent_id: int) -> None:
        if agent_id not in self._names:
            raise ValueError(f"Unknown agent id: {agent_id}")

    @tool(readonly=True, kind="observe")
    async def observe_social_space(self, agent_id: int) -> dict:
        """Observe public participant names and messages addressed to this agent."""
        self._require_agent(agent_id)
        return {
            "self": {"id": agent_id, "name": self._names[agent_id]},
            "participants": [
                {"id": other_id, "name": name}
                for other_id, name in sorted(self._names.items())
            ],
            "inbox": list(self._inboxes[agent_id]),
        }

    @tool(readonly=False)
    async def send_message(self, agent_id: int, recipient_id: int, content: str) -> dict:
        """Send one addressed message to the other registered agent."""
        self._require_agent(agent_id)
        self._require_agent(recipient_id)
        if agent_id == recipient_id:
            raise ValueError("Agents may not send social messages to themselves.")

        text = str(content).strip()
        if not text:
            raise ValueError("Message content may not be empty.")

        message = {
            "id": self._next_message_id,
            "from_id": agent_id,
            "from_name": self._names[agent_id],
            "to_id": recipient_id,
            "to_name": self._names[recipient_id],
            "content": text,
        }
        self._next_message_id += 1
        self._inboxes[recipient_id].append(message)
        return {"success": True, "message": message}

    @tool(readonly=False)
    async def consume_message(self, agent_id: int, message_id: int) -> dict:
        """Remove one addressed message after the recipient has processed it."""
        self._require_agent(agent_id)
        inbox = self._inboxes[agent_id]
        for index, message in enumerate(inbox):
            if int(message["id"]) == int(message_id):
                removed = inbox.pop(index)
                return {"success": True, "message": removed}
        return {"success": False, "reason": "message_not_found", "message_id": int(message_id)}

    async def step(self, tick: int, t: datetime):
        """Advance environment time without generating messages or actions."""
        self.t = t
