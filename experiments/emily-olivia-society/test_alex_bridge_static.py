#!/usr/bin/env python3
"""Cheap invariants for the external Alex participant path."""
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    agents = (HERE / "agents.json").read_text(encoding="utf-8")
    bridge = (HERE / "alex_bridge.py").read_text(encoding="utf-8")
    social = (HERE / "social_bridge.py").read_text(encoding="utf-8")
    exchange = (HERE / "first_exchange.py").read_text(encoding="utf-8")

    assert '"name": "Alex"' not in agents, "Alex must not become an autonomous agent spec"
    assert 'ALEX_ID = 3' in bridge and 'ALEX_NAME = "Alex"' in bridge
    assert 'ISSUE_NUMBER = 277' in bridge
    assert 'ALEX_GITHUB_LOGIN = "maaronfanberg-lab"' in bridge
    assert '_ACK_REACTION = "eyes"' in bridge
    assert 'GH_TOKEN' in bridge
    assert 'ACTIONS_ID_TOKEN' not in bridge
    assert '(3, "Alex")' in social, "Alex must be a registered external social participant"
    assert "AlexParticipant()" in exchange
    assert "choose_action(agent, observation, partner" in exchange
    assert "acknowledge_alex" in exchange
    assert "continuation_relay" in exchange
    print("Alex GitHub-doorway invariants: ok")


if __name__ == "__main__":
    main()
