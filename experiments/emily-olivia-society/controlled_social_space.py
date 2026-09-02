from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from agentsociety2.env import EnvBase, tool

MAX_MESSAGE_CHARS = 12_000
STATE_VERSION = 1


class ControlledSocialSpace(EnvBase):
    """Small registered social boundary built with AgentSociety 2 tools."""

    def __init__(
        self,
        agent_id_name_pairs: list[tuple[int, str]],
        state_path: str | Path | None = None,
    ):
        super().__init__()
        if len(agent_id_name_pairs) < 2:
            raise ValueError("ControlledSocialSpace requires at least two participants.")
        self._names = {int(agent_id): str(name) for agent_id, name in agent_id_name_pairs}
        if len(self._names) != len(agent_id_name_pairs):
            raise ValueError("Participant IDs must be unique.")
        if any(not name.strip() for name in self._names.values()):
            raise ValueError("Participant names must be non-empty.")

        self._state_path = Path(state_path) if state_path is not None else None
        self._inboxes: dict[int, list[dict]] = {agent_id: [] for agent_id in self._names}
        self._next_message_id = 1
        self.t: datetime | None = None
        self._load_state()

    @classmethod
    def description(cls) -> str:
        return "A private-by-default registered social space with addressed messaging."

    @classmethod
    def init_description(cls) -> str:
        return """ControlledSocialSpace

A registered social environment built with AgentSociety 2 EnvBase and @tool.

Available tools:
- observe_social_space(agent_id): read-only; returns participant names and that participant's addressed inbox.
- send_message(agent_id, recipient_id, content): mutating; sends one explicit message to another registered participant.
- consume_message(agent_id, message_id): mutating; removes one addressed message after it has been processed.

Only Emily and Olivia have autonomous cognition. Alex is a registered external human participant.
Private cognition workspaces and memory files are not exposed by this environment.
"""

    def _require_agent(self, agent_id: int) -> None:
        if agent_id not in self._names:
            raise ValueError(f"Unknown participant id: {agent_id}")

    def _validate_message(self, message: object, expected_to: int) -> dict:
        if not isinstance(message, dict):
            raise ValueError("Persisted inbox message must be an object.")
        required = ("id", "from_id", "from_name", "to_id", "to_name", "content")
        if any(key not in message for key in required):
            raise ValueError("Persisted inbox message is missing required fields.")
        message_id = int(message["id"])
        from_id = int(message["from_id"])
        to_id = int(message["to_id"])
        if message_id < 1 or from_id not in self._names or to_id not in self._names or to_id != expected_to or from_id == to_id:
            raise ValueError("Persisted inbox message has invalid routing metadata.")
        content = str(message["content"]).strip()
        if not content or len(content) > MAX_MESSAGE_CHARS:
            raise ValueError("Persisted inbox message has invalid content length.")
        validated = dict(message)
        validated.update({
            "id": message_id,
            "from_id": from_id,
            "from_name": self._names[from_id],
            "to_id": to_id,
            "to_name": self._names[to_id],
            "content": content,
        })
        return validated

    def _load_state(self) -> None:
        if self._state_path is None or not self._state_path.exists():
            return
        payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or int(payload.get("version", 0)) != STATE_VERSION:
            raise ValueError("Unsupported or malformed social state.")
        inboxes = payload.get("inboxes")
        if not isinstance(inboxes, dict):
            raise ValueError("Social state inboxes must be an object.")

        restored: dict[int, list[dict]] = {}
        seen_ids: set[int] = set()
        max_id = 0
        for agent_id in self._names:
            raw_inbox = inboxes.get(str(agent_id), [])
            if not isinstance(raw_inbox, list):
                raise ValueError(f"Inbox for participant {agent_id} must be a list.")
            restored[agent_id] = []
            for raw_message in raw_inbox:
                message = self._validate_message(raw_message, agent_id)
                if message["id"] in seen_ids:
                    raise ValueError(f"Duplicate persisted message id: {message['id']}")
                seen_ids.add(message["id"])
                max_id = max(max_id, message["id"])
                restored[agent_id].append(message)
        self._inboxes = restored
        declared_next = int(payload.get("next_message_id", 1))
        self._next_message_id = max(1, declared_next, max_id + 1)

    def _save_state(self) -> None:
        if self._state_path is None:
            return
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": STATE_VERSION,
            "next_message_id": self._next_message_id,
            "inboxes": {str(agent_id): inbox for agent_id, inbox in self._inboxes.items()},
        }
        tmp_path = self._state_path.with_suffix(self._state_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        tmp_path.replace(self._state_path)

    @tool(readonly=True, kind="observe")
    async def observe_social_space(self, agent_id: int) -> dict:
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
        self._require_agent(agent_id)
        self._require_agent(recipient_id)
        if agent_id == recipient_id:
            raise ValueError("Participants may not send social messages to themselves.")

        text = str(content).strip()
        if not text:
            raise ValueError("Message content may not be empty.")
        if len(text) > MAX_MESSAGE_CHARS:
            raise ValueError(f"Message content exceeds {MAX_MESSAGE_CHARS} characters.")

        message = {
            "id": self._next_message_id,
            "from_id": agent_id,
            "from_name": self._names[agent_id],
            "to_id": recipient_id,
            "to_name": self._names[recipient_id],
            "content": text,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._next_message_id += 1
        self._inboxes[recipient_id].append(message)
        self._save_state()
        return {"success": True, "message": message}

    @tool(readonly=False)
    async def consume_message(self, agent_id: int, message_id: int) -> dict:
        self._require_agent(agent_id)
        if int(message_id) < 1:
            raise ValueError("message_id must be positive.")
        inbox = self._inboxes[agent_id]
        for index, message in enumerate(inbox):
            if int(message["id"]) == int(message_id):
                removed = inbox.pop(index)
                self._save_state()
                return {"success": True, "message": removed}
        return {"success": False, "reason": "message_not_found", "message_id": int(message_id)}

    async def step(self, tick: int, t: datetime):
        self.t = t
