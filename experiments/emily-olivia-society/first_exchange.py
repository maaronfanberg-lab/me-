#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import selectors
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

from alex_bridge import ALEX_ID, ALEX_NAME, AlexBridgeClient, AlexParticipant
from community_cycle import (
    load_agents,
    observation_text,
    choose_action,
    next_community_time_step,
)

HERE = Path(__file__).resolve().parent
REPLAY_DIR = HERE / "replay"
AGENTSOCIETY_PYTHON = HERE / ".venv-agentsociety" / "bin" / "python"
BRIDGE = HERE / "social_bridge.py"
_MAX_RECOVERABLE_SPEECH_ATTEMPTS = 3
_RECOVERABLE_SPEECH_FAILURE_MARKERS = (
    "paper-derived Stanford act repeatedly crossed the live dialogue grounding boundary",
    "repeatedly hit structural dialogue blockers after",
    "paper-derived Stanford act failed the dialogue boundary",
)


class SocialBridgeClient:
    """Keep Stanford and AgentSociety dependencies in separate processes."""

    def __init__(self) -> None:
        if not AGENTSOCIETY_PYTHON.exists():
            raise SystemExit("AgentSociety environment is missing. Run bootstrap_upstreams.sh first.")
        try:
            self.rpc_timeout = float(os.environ.get("COMMUNITY_SOCIAL_RPC_TIMEOUT", "30"))
        except ValueError as exc:
            raise RuntimeError("COMMUNITY_SOCIAL_RPC_TIMEOUT must be numeric.") from exc
        if not 1 <= self.rpc_timeout <= 300:
            raise RuntimeError("COMMUNITY_SOCIAL_RPC_TIMEOUT must be between 1 and 300 seconds.")

        self.alex = AlexBridgeClient()
        bridge_env = os.environ.copy()
        bridge_env.setdefault("AGENTSOCIETY_LLM_API_KEY", "local-no-api-key")
        self.proc = subprocess.Popen(
            [str(AGENTSOCIETY_PYTHON), "-u", str(BRIDGE)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=bridge_env,
        )
        if self.proc.stdout is None:
            self._force_stop()
            raise RuntimeError("Social bridge stdout is unavailable.")
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.proc.stdout, selectors.EVENT_READ)

    def _dead_error(self) -> RuntimeError:
        stderr = ""
        if self.proc.stderr is not None and self.proc.poll() is not None:
            stderr = self.proc.stderr.read().strip()
        detail = stderr or f"exit code {self.proc.returncode}"
        return RuntimeError(f"Social bridge exited unexpectedly: {detail}")

    def _call(self, payload: dict) -> dict:
        if self.proc.poll() is not None:
            raise self._dead_error()
        if self.proc.stdin is None or self.proc.stdout is None:
            raise RuntimeError("Social bridge pipes are unavailable.")

        op = str(payload.get("op", "unknown"))
        try:
            self.proc.stdin.write(json.dumps(payload) + "\n")
            self.proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            if self.proc.poll() is not None:
                raise self._dead_error() from exc
            raise RuntimeError(f"Social bridge write failed during {op}: {exc}") from exc

        events = self.selector.select(timeout=self.rpc_timeout)
        if not events:
            if self.proc.poll() is not None:
                raise self._dead_error()
            raise TimeoutError(
                f"Social bridge RPC '{op}' exceeded {self.rpc_timeout:g} seconds."
            )

        line = self.proc.stdout.readline()
        if not line:
            raise self._dead_error()
        try:
            response = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Social bridge returned invalid JSON during {op}.") from exc
        if not isinstance(response, dict):
            raise RuntimeError(f"Social bridge returned a non-object response during {op}.")
        if response.get("ok") is not True:
            raise RuntimeError(str(response.get("error", "Unknown social bridge error")))
        result = response.get("result")
        if not isinstance(result, dict):
            raise RuntimeError(f"Social bridge returned an invalid result during {op}.")
        return result

    async def observe_social_space(self, agent_id: int) -> dict:
        return self._call({"op": "observe", "agent_id": agent_id})

    async def send_message(self, agent_id: int, recipient_id: int, content: str) -> dict:
        return self._call(
            {
                "op": "send",
                "agent_id": agent_id,
                "recipient_id": recipient_id,
                "content": content,
            }
        )

    async def consume_message(self, agent_id: int, message_id: int) -> dict:
        return self._call(
            {"op": "consume", "agent_id": agent_id, "message_id": message_id}
        )

    async def first_alex_for(self, agent_name: str) -> dict | None:
        return self.alex.first_for(agent_name)

    async def acknowledge_alex(self, queue_id: str) -> dict:
        return self.alex.ack([queue_id])

    def _force_stop(self) -> None:
        if self.proc.poll() is not None:
            return
        self.proc.terminate()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=3)

    def close(self) -> None:
        try:
            if self.proc.poll() is None:
                try:
                    self._call({"op": "close"})
                    self.proc.wait(timeout=5)
                except Exception:
                    self._force_stop()
        finally:
            try:
                self.selector.close()
            except Exception:
                pass
            for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass


def _coerce_memory_importance(agent) -> None:
    """Keep Stanford retrieval numeric even when the local model grades importance as text."""
    for node in agent.brain.memory_stream.seq_nodes:
        value = getattr(node, "importance", 0)
        if isinstance(value, bool):
            value = int(value)
        if isinstance(value, (int, float)):
            numeric = float(value)
        else:
            match = re.search(r"-?\d+(?:\.\d+)?", str(value))
            numeric = float(match.group(0)) if match else 0.0
        numeric = max(0.0, min(100.0, numeric))
        node.importance = int(numeric) if numeric.is_integer() else numeric


def _memory_already_present(agent, memory: str, window: int = 32) -> bool:
    """Make re-observing an unconsumed social message idempotent across restarts."""
    target = str(memory or "").strip()
    if not target:
        return True
    nodes = list(getattr(agent.brain.memory_stream, "seq_nodes", []) or [])
    for node in reversed(nodes[-max(1, window):]):
        if str(getattr(node, "content", "")).strip() == target:
            return True
    return False


def _recoverable_speech_failure(exc: RuntimeError) -> bool:
    message = str(exc)
    return any(marker in message for marker in _RECOVERABLE_SPEECH_FAILURE_MARKERS)


def _alex_observation(base: dict, agent, item: dict) -> dict:
    participants = list(base.get("participants", []) or [])
    if not any(int(row.get("id", -1)) == ALEX_ID for row in participants if isinstance(row, dict)):
        participants.append({"id": ALEX_ID, "name": ALEX_NAME})
    return {
        "self": dict(base.get("self", {"id": agent.agent_id, "name": agent.name})),
        "participants": participants,
        "inbox": [
            {
                "id": f"alex-{item['id']}",
                "from_id": ALEX_ID,
                "from_name": ALEX_NAME,
                "to_id": agent.agent_id,
                "to_name": agent.name,
                "content": item["text"],
                "created_at": item.get("at") or datetime.now(timezone.utc).isoformat(),
            }
        ],
    }


async def process_one_reply(
    agent,
    other,
    social,
    time_step: int,
    dialogue_history: list[tuple[str, str]] | None = None,
) -> dict:
    observation = await social.observe_social_space(agent.agent_id)
    inbox = observation.get("inbox", [])
    alex_item = await social.first_alex_for(agent.name)
    interrupted_inbound = None
    partner = other

    if alex_item is not None:
        # Alex entering the room interrupts the currently pending peer reply. The
        # agent still observes/remembers that peer line before it is consumed, so
        # nothing already spoken disappears from cognition merely because a human
        # joined the conversation.
        if inbox:
            interrupted_inbound = dict(inbox[-1])
            interrupted_memory = observation_text(agent, observation)
            if not _memory_already_present(agent, interrupted_memory):
                agent.brain.remember(interrupted_memory, time_step=time_step)
            interrupted_consume = await social.consume_message(agent.agent_id, int(interrupted_inbound["id"]))
            if interrupted_consume.get("success") is not True:
                raise RuntimeError(f"Failed to consume interrupted peer message for {agent.name}.")
        observation = _alex_observation(observation, agent, alex_item)
        inbox = observation["inbox"]
        partner = AlexParticipant()
        if dialogue_history is not None:
            human_line = (ALEX_NAME, str(alex_item["text"]))
            if not dialogue_history or dialogue_history[-1] != human_line:
                dialogue_history.append(human_line)
        if str(alex_item.get("target")) == "both":
            other_memory = f"{other.name} observes a message from Alex: {alex_item['text']}"
            if not _memory_already_present(other, other_memory):
                other.brain.remember(other_memory, time_step=time_step)
                _coerce_memory_importance(other)
                other.brain.save(str(other.workspace))

    if not inbox:
        return {"agent": agent.name, "action": {"type": "wait", "reason": "no_new_message"}}

    latest = inbox[-1]
    memory = observation_text(agent, observation)
    if not _memory_already_present(agent, memory):
        agent.brain.remember(memory, time_step=time_step)
    _coerce_memory_importance(agent)

    # No authored fallback is used. A recoverable speech-boundary exhaustion
    # keeps the exact inbound unread and retries the full Stanford-derived act
    # on that same turn. Only after a bounded number of fresh stochastic passes
    # do we defer the message for a later pulse/run.
    generation_errors: list[str] = []
    action = None
    for _speech_attempt in range(_MAX_RECOVERABLE_SPEECH_ATTEMPTS):
        try:
            action = choose_action(agent, observation, partner, dialogue_history=dialogue_history)
            break
        except RuntimeError as exc:
            if not _recoverable_speech_failure(exc):
                raise
            generation_errors.append(str(exc))

    if action is None:
        agent.brain.save(str(agent.workspace))
        return {
            "agent": agent.name,
            "time_step": time_step,
            "observation": observation,
            "retrieved_memories": [],
            "retrieved_memory_evidence": [],
            "action": {"type": "wait", "reason": "speech_generation_deferred"},
            "action_result": None,
            "consumed_inbound": False,
            "external_inbound": alex_item,
            "interrupted_inbound": interrupted_inbound,
            "generation_deferred": True,
            "generation_attempts": _MAX_RECOVERABLE_SPEECH_ATTEMPTS,
            "generation_error": " || ".join(generation_errors),
        }

    # The act itself carries the exact filtered Stanford reaction retrieval that
    # reached the speech prompt. Do not run a second retrieval just for reporting.
    relevant = list(action.get("retrieved_memories", []) or [])
    retrieval_metadata = list(action.get("retrieved_memory_evidence", []) or [])

    result = None
    consumed = False
    relay_result = None
    alex_ack = None
    if action["type"] == "message":
        if alex_item is not None:
            # Alex is human, so there is no autonomous recipient process to send
            # into. Persist the real Stanford act as the delivered reply to Alex,
            # and relay the same spoken line to the other autonomous participant
            # so the group conversation continues naturally on the next turn.
            result = {
                "success": True,
                "message": {
                    "id": f"alex-reply-{uuid.uuid4().hex}",
                    "from_id": agent.agent_id,
                    "from_name": agent.name,
                    "to_id": ALEX_ID,
                    "to_name": ALEX_NAME,
                    "content": str(action["content"]),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            }
            relay_result = await social.send_message(
                agent.agent_id,
                other.agent_id,
                str(action["content"]),
            )
            if not isinstance(relay_result, dict) or relay_result.get("success") is not True:
                raise RuntimeError(f"Failed to keep the room conversation moving after {agent.name} replied to Alex.")
            alex_ack = await social.acknowledge_alex(str(alex_item["id"]))
            if int(alex_ack.get("acknowledged", 0) or 0) < 1:
                raise RuntimeError("Alex turn was answered but could not be acknowledged.")
            consumed = True
        else:
            result = await social.send_message(
                agent.agent_id,
                int(action["recipient_id"]),
                str(action["content"]),
            )
            if not isinstance(result, dict) or result.get("success") is not True:
                raise RuntimeError(f"Message delivery failed for {agent.name}.")
            consume_result = await social.consume_message(agent.agent_id, int(latest["id"]))
            if consume_result.get("success") is not True:
                raise RuntimeError(f"Message consume failed for {agent.name}.")
            consumed = True

    agent.brain.save(str(agent.workspace))

    return {
        "agent": agent.name,
        "time_step": time_step,
        "observation": observation,
        "retrieved_memories": relevant,
        "retrieved_memory_evidence": retrieval_metadata,
        "action": action,
        "action_result": result,
        "consumed_inbound": consumed,
        "external_inbound": alex_item,
        "interrupted_inbound": interrupted_inbound,
        "continuation_relay": relay_result,
        "external_ack": alex_ack,
    }


async def run_first_exchange(opener: str) -> dict:
    opener = str(opener or "").strip()
    if not opener:
        raise ValueError("first_exchange requires an explicit opener; it has no canned default or fallback.")

    agents = load_agents()
    emily = next(a for a in agents if a.name == "Emily")
    olivia = next(a for a in agents if a.name == "Olivia")
    social = SocialBridgeClient()
    base_time_step = next_community_time_step(agents)
    dialogue_history: list[tuple[str, str]] = [(emily.name, opener)]

    try:
        seed = await social.send_message(emily.agent_id, olivia.agent_id, opener)
        olivia_turn = await process_one_reply(
            olivia,
            emily,
            social,
            time_step=base_time_step,
            dialogue_history=dialogue_history,
        )
        if olivia_turn.get("action", {}).get("type") == "message":
            dialogue_history.append((olivia.name, str(olivia_turn["action"]["content"])))
        emily_turn = await process_one_reply(
            emily,
            olivia,
            social,
            time_step=base_time_step + 1,
            dialogue_history=dialogue_history,
        )
    finally:
        social.close()

    transcript = {
        "mode": "bounded_first_exchange",
        "limits": {
            "seed_messages": 1,
            "reply_turns": 2,
            "autonomous_loop": False,
        },
        "start_time_step": base_time_step,
        "seed": seed,
        "turns": [olivia_turn, emily_turn],
    }

    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    (REPLAY_DIR / "first_exchange.json").write_text(
        json.dumps(transcript, indent=2),
        encoding="utf-8",
    )
    return transcript


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the first bounded Emily + Olivia exchange.")
    parser.add_argument(
        "--opener",
        default="",
        help="Explicit initial message from Emily to Olivia; no default dialogue is supplied.",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help="Explicitly permit one seed message, Olivia's reply, and Emily's reply, then stop.",
    )
    args = parser.parse_args()

    if not args.run:
        raise SystemExit("Refusing to start automatically. Use --run for exactly one bounded first exchange.")

    result = await run_first_exchange(args.opener)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
