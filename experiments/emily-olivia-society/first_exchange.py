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
# The paper sampler already owns bounded stochastic retries. One choose_action
# pass keeps a turn responsive; continuous_session retries a deferred, unconsumed
# inbound on the next loop instead of multiplying hidden model calls here.
_MAX_RECOVERABLE_SPEECH_ATTEMPTS = 1
_RECOVERABLE_SPEECH_FAILURE_MARKERS = (
    "paper-derived Stanford act repeatedly crossed the live dialogue grounding boundary",
    "repeatedly hit structural dialogue blockers after",
    "paper-derived Stanford act failed the dialogue boundary",
    "paper-derived Stanford act produced no usable spoken line after",
    "Remote end closed connection without response",
    "BitNet paper-act completion request failed",
    "BitNet paper-act completion HTTP 408",
    "BitNet paper-act completion HTTP 429",
    "BitNet paper-act completion HTTP 500",
    "BitNet paper-act completion HTTP 502",
    "BitNet paper-act completion HTTP 503",
    "BitNet paper-act completion HTTP 504",
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
            raise RuntimeError("Social bridge returned a non-object response during {op}.")
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


async def _choose_with_recovery(agent, observation: dict, partner, dialogue_history):
    errors: list[str] = []
    for _speech_attempt in range(_MAX_RECOVERABLE_SPEECH_ATTEMPTS):
        try:
            return choose_action(agent, observation, partner, dialogue_history=dialogue_history), errors
        except RuntimeError as exc:
            if not _recoverable_speech_failure(exc):
                raise
            errors.append(str(exc))
    return None, errors


async def process_one_reply(
    agent,
    other,
    social,
    time_step: int,
    dialogue_history: list[tuple[str, str]] | None = None,
) -> dict:
    peer_observation = await social.observe_social_space(agent.agent_id)
    peer_inbox = peer_observation.get("inbox", [])
    alex_item = await social.first_alex_for(agent.name)

    external_action = None
    external_result = None
    external_ack = None
    external_generation_errors: list[str] = []

    # Alex is a side-channel participant, not a substitute for the pending
    # Emily<->Olivia turn. Answer Alex through the same Stanford cognition, but
    # do not inject Alex's verbatim wording into the autonomous pair's persistent
    # memory stream. That wording remains available during the direct Alex turn,
    # then disappears from peer retrieval so a distinctive short Alex phrase
    # cannot later be spoken as if Emily or Olivia coined it.
    if alex_item is not None:
        if peer_inbox:
            peer_memory = observation_text(agent, peer_observation)
            if not _memory_already_present(agent, peer_memory):
                agent.brain.remember(peer_memory, time_step=time_step)

        alex_observation = _alex_observation(peer_observation, agent, alex_item)
        _coerce_memory_importance(agent)

        external_action, external_generation_errors = await _choose_with_recovery(
            agent,
            alex_observation,
            AlexParticipant(),
            dialogue_history,
        )
        if external_action is not None and external_action.get("type") == "message":
            external_result = {
                "success": True,
                "message": {
                    "id": f"alex-reply-{uuid.uuid4().hex}",
                    "from_id": agent.agent_id,
                    "from_name": agent.name,
                    "to_id": ALEX_ID,
                    "to_name": ALEX_NAME,
                    "content": str(external_action["content"]),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
            }
            external_ack = await social.acknowledge_alex(str(alex_item["id"]))
            if int(external_ack.get("acknowledged", 0) or 0) < 1:
                raise RuntimeError("Alex turn was answered but could not be acknowledged.")

    if not peer_inbox:
        agent.brain.save(str(agent.workspace))
        return {
            "agent": agent.name,
            "time_step": time_step,
            "observation": peer_observation,
            "retrieved_memories": [],
            "retrieved_memory_evidence": [],
            "action": {"type": "wait", "reason": "no_new_message"},
            "action_result": None,
            "consumed_inbound": False,
            "external_inbound": alex_item,
            "external_action": external_action,
            "external_action_result": external_result,
            "external_ack": external_ack,
            "external_generation_error": " || ".join(external_generation_errors),
        }

    latest = peer_inbox[-1]
    memory = observation_text(agent, peer_observation)
    if not _memory_already_present(agent, memory):
        agent.brain.remember(memory, time_step=time_step)
    _coerce_memory_importance(agent)

    action, generation_errors = await _choose_with_recovery(
        agent,
        peer_observation,
        other,
        dialogue_history,
    )

    if action is None:
        agent.brain.save(str(agent.workspace))
        return {
            "agent": agent.name,
            "time_step": time_step,
            "observation": peer_observation,
            "retrieved_memories": [],
            "retrieved_memory_evidence": [],
            "action": {"type": "wait", "reason": "speech_generation_deferred"},
            "action_result": None,
            "consumed_inbound": False,
            "external_inbound": alex_item,
            "external_action": external_action,
            "external_action_result": external_result,
            "external_ack": external_ack,
            "external_generation_error": " || ".join(external_generation_errors),
            "generation_deferred": True,
            "generation_attempts": _MAX_RECOVERABLE_SPEECH_ATTEMPTS,
            "generation_error": " || ".join(generation_errors),
        }

    relevant = list(action.get("retrieved_memories", []) or [])
    retrieval_metadata = list(action.get("retrieved_memory_evidence", []) or [])

    result = None
    consumed = False
    if action["type"] == "message":
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
        "observation": peer_observation,
        "retrieved_memories": relevant,
        "retrieved_memory_evidence": retrieval_metadata,
        "action": action,
        "action_result": result,
        "consumed_inbound": consumed,
        "external_inbound": alex_item,
        "external_action": external_action,
        "external_action_result": external_result,
        "external_ack": external_ack,
        "external_generation_error": " || ".join(external_generation_errors),
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
        "seed": seed,
        "olivia_turn": olivia_turn,
        "emily_turn": emily_turn,
    }
    REPLAY_DIR.mkdir(parents=True, exist_ok=True)
    (REPLAY_DIR / "first_exchange.json").write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    return transcript


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("opener")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run_first_exchange(args.opener)), indent=2))


if __name__ == "__main__":
    main()