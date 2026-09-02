#!/usr/bin/env python3
"""Cheap invariants for the external Alex participant path.

No network or model call is made here. This exists so CI can catch accidental
regressions that turn Alex into an autonomous agent or leak the private user key.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    agents = (HERE / "agents.json").read_text(encoding="utf-8")
    bridge = (HERE / "alex_bridge.py").read_text(encoding="utf-8")
    social = (HERE / "social_bridge.py").read_text(encoding="utf-8")
    exchange = (HERE / "first_exchange.py").read_text(encoding="utf-8")
    worker = (HERE.parent.parent / "cloudflare" / "emily-olivia-community" / "src" / "index.js")

    assert '"name": "Alex"' not in agents, "Alex must not become an autonomous agent spec"
    assert 'ALEX_ID = 3' in bridge and 'ALEX_NAME = "Alex"' in bridge
    assert '(3, "Alex")' in social, "Alex must be a registered external social participant"
    assert "AlexParticipant()" in exchange
    assert "choose_action(agent, observation, partner" in exchange
    assert "acknowledge_alex" in exchange
    assert "continuation_relay" in exchange
    assert worker.is_file(), "Emily Olivia worker source is missing"
    worker_text = worker.read_text(encoding="utf-8")
    assert "/api/alex/pending" in worker_text and "/api/alex/ack" in worker_text
    assert "ALEX_KEY_SHA256" in worker_text
    assert "0jxQXiL4dsfZOf5vIpZdBeALI_pC5SQJAaWLhTCDhNo" not in worker_text, "plaintext Alex key leaked"
    print("Alex external-participant invariants: ok")


if __name__ == "__main__":
    main()
