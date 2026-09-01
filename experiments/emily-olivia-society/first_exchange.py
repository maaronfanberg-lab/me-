#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import selectors
import subprocess
from pathlib import Path

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


async def process_one_reply(
    agent,
    other,
    social,
    time_step: int,
    dialogue_history: list[tuple[str, str]] | None = None,
) -> dict:
    observation = await social.observe_social_space(agent.agent_id)
    inbox = observation.get("inbox", [])
    if not inbox:
        return {"agent": agent.name, "action": {"type": "wait", "reason": "no_new_message"}}

    latest = inbox[-1]
    memory = observation_text(agent, observation)
    agent.brain.remember(memory, time_step=time_step)
    _coerce_memory_importance(agent)

    query = f"Current interaction with {other.name}"
    retrieved = agent.brain.memory_stream.retrieve([query], time_step=time_step, n_count=12)
    relevant = [node.content for node in retrieved.get(query, [])]

    # There is intentionally no authored fallback here. If Stanford cognition
    # cannot produce an action, the run fails with its evidence intact rather
    # than replacing the agent's speech with local canned dialogue.
    action = choose_action(agent, observation, other, dialogue_history=dialogue_history)

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
        "observation": observation,
        "retrieved_memories": relevant,
        "action": action,
        "action_result": result,
        "consumed_inbound": consumed,
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
