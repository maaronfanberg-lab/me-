#!/usr/bin/env python3
"""Native DeepMind Concordia Room runner, using the published engine and GM.

This is a separate proof-of-integration entry point. It does NOT silently
replace the production Room or mutate its public conversation ledger.
Run with --mode scripted for a deterministic upstream-engine smoke test.
Run with --mode llama only while the existing local llama-server is running.
"""
from __future__ import annotations

import argparse
from collections.abc import Collection, Mapping, Sequence
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import urllib.parse
import urllib.request
from typing import Any

import numpy as np
from concordia.agents import entity_agent_with_logging
from concordia.associative_memory import basic_associative_memory
from concordia.components import agent as agent_components
from concordia.environment.engines import simultaneous
from concordia.language_model import language_model, no_language_model
from concordia.prefabs.game_master import interrupt_driven

PARTICIPANTS = ("sarah", "mara", "owen", "jules")
ROOT = Path(__file__).resolve().parents[1]


def embed(text: str) -> np.ndarray:
    """Reproducible local embedding for the integration test, NOT semantic SOTA."""
    vec = np.zeros(256, dtype=np.float32)
    for token in re.findall(r"[a-z0-9]+", str(text).lower()):
        hashed = hashlib.blake2b(token.encode(), digest_size=4).digest()
        position = int.from_bytes(hashed, "big") % len(vec)
        vec[position] += 1
    size = float(np.linalg.norm(vec))
    if size:
        vec /= size
    return vec


def identity_text(name: str, config: Mapping[str, Any]) -> str:
    """Use the Room's actual character definitions, not a replacement cast."""
    profile = ((config.get("p") or {}).get(name.lower()) or {})
    psyche = profile.get("psychology_v2") or {}
    elements = [
        str(psyche.get("core_identity") or name),
        str(psyche.get("agency_style") or ""),
        "Personal motives: " + "; ".join(map(str, (psyche.get("motives") or [])[:4])),
        "Act independently, including working quietly when that is genuinely appropriate.",
        "Never invent another person's speech or turn a plan into an accomplished action.",
    ]
    return "\n".join(x for x in elements if x.strip())


class LocalLlama(language_model.LanguageModel):
    """Adapter from Concordia's real LanguageModel interface to Room llama.cpp."""

    def __init__(self, url: str, model_id: str) -> None:
        address = urllib.parse.urlsplit(url)
        if address.scheme != "http" or address.hostname not in ("127.0.0.1", "localhost"):
            raise ValueError("Concordia pilot accepts only the Room's local llama-server")
        if address.path != "/v1/chat/completions":
            raise ValueError("Expected llama.cpp's /v1/chat/completions endpoint")
        self.url, self.model_id = url, model_id

    def sample_text(
        self,
        prompt: str,
        *,
        max_tokens: int = language_model.DEFAULT_MAX_TOKENS,
        terminators: Collection[str] = language_model.DEFAULT_TERMINATORS,
        temperature: float = language_model.DEFAULT_TEMPERATURE,
        top_p: float = language_model.DEFAULT_TOP_P,
        top_k: int = language_model.DEFAULT_TOP_K,
        timeout: float = language_model.DEFAULT_TIMEOUT_SECONDS,
        seed: int | None = None,
    ) -> str:
        body: dict[str, Any] = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": min(int(max_tokens), 600),
            "temperature": max(0.05, min(float(temperature), 1.2)),
            "top_p": float(top_p),
            "stream": False,
        }
        if seed is not None:
            body["seed"] = seed
        request = urllib.request.Request(
            self.url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=min(90, max(5, timeout))) as reply:
            result = json.load(reply)
        choices = result.get("choices") or []
        output = str((choices[0].get("message") or {}).get("content") or "") if choices else ""
        if not output.strip():
            raise RuntimeError("Local llama-server returned empty Concordia action")
        for stop in terminators:
            if stop and stop in output:
                output = output.split(stop, 1)[0]
        return output

    def sample_choice(
        self,
        prompt: str,
        responses: Sequence[str],
        *,
        seed: int | None = None,
    ) -> tuple[int, str, Mapping[str, Any]]:
        if not responses:
            raise ValueError("No choices")
        options = "\n".join(f"{i}: {value}" for i, value in enumerate(responses))
        answer = self.sample_text(
            prompt + "\n\nSelect ONE choice by its integer index only:\n" + options,
            max_tokens=15, temperature=0.1, seed=seed,
        )
        index_match = re.search(r"\b\d+\b", answer)
        if index_match is None:
            raise language_model.InvalidResponseError("No choice index in model output")
        idx = int(index_match.group())
        if not 0 <= idx < len(responses):
            raise language_model.InvalidResponseError("Choice index outside supplied options")
        return idx, responses[idx], {}


class ScriptedModel(no_language_model.NoLanguageModel):
    """Deterministic fixture, used ONLY to test the genuine Concordia engine."""

    def __init__(self) -> None:
        super().__init__()
        self.lock = threading.Lock()
        self.calls: list[str] = []

    def sample_text(self, prompt: str, **kwargs: Any) -> str:
        del kwargs
        match = re.findall(r"What does (Sarah|Mara|Owen|Jules) do next\?", prompt)
        if not match:
            raise RuntimeError("Unexpected Concordia action prompt")
        name = match[-1]
        with self.lock:
            self.calls.append(name)
        if name == "Mara":
            action = "I ask Jules whether she saw the notebook."
        elif name == "Jules":
            action = "I check the notebook while the others work."
        else:
            action = ""
        return action + '\n{"mask": [], "timer": {"time": "45m", "reason": "resume own work"}}'


def build_agents(model: language_model.LanguageModel, config: Mapping[str, Any]):
    """Instantiate four native Concordia entities from the existing Room cast."""
    sleeping = {str(x).lower() for x in config.get("sleeping_entities", [])}
    players = []
    for name in PARTICIPANTS:
        if name in sleeping:
            continue
        key = name.capitalize()
        memory_bank = basic_associative_memory.AssociativeMemoryBank(
            sentence_embedder=embed,
        )
        components = {
            "identity": agent_components.constant.Constant(
                state=identity_text(name, config),
                pre_act_label="Your identity and independent interests",
            ),
            agent_components.memory.DEFAULT_MEMORY_COMPONENT_KEY:
                agent_components.memory.AssociativeMemory(
                    memory_bank=memory_bank,
                ),
            "observation_to_memory": agent_components.observation.ObservationToMemory(),
            "observations": agent_components.observation.LastNObservations(
                history_length=24,
            ),
        }
        actor = agent_components.concat_act_component.ConcatActComponent(
            model=model,
            component_order=list(components),
            prefix_entity_name=False,
        )
        players.append(
            entity_agent_with_logging.EntityAgentWithLogging(
                agent_name=key,
                act_component=actor,
                context_components=components,
            )
        )
    if not players:
        raise ValueError("All Room characters are sleeping")
    return players


def run(
    *,
    mode: str,
    steps: int = 5,
    root: Path = ROOT,
    start_time: str = "2026-11-09T09:00:00",
    user_event: str = "",
    llama_url: str = "http://127.0.0.1:18080/v1/chat/completions",
) -> dict[str, Any]:
    config = json.loads((root / "room" / "config.json").read_text(encoding="utf-8"))
    model = (
        ScriptedModel()
        if mode == "scripted"
        else LocalLlama(llama_url, os.getenv("ROOM_CHAT_MODEL_ID", "Llama-3.2-3B-Instruct"))
    )
    players = build_agents(model, config)
    names = [p.name for p in players]

    if mode == "scripted":
        # Exact selective-attention regression: two entities are busy,
        # only two hear the invitation. No compulsory four-speaker beat.
        initial_states = {
            "Sarah": {"mask": ["emergency."], "timer_duration": "45m"},
            "Mara": {"mask": [""], "timer_duration": "15m"},
            "Owen": {"mask": ["logic."], "timer_duration": "1h"},
            "Jules": {"mask": [""], "timer_duration": "20m"},
        }
        initial_events = [{
            "timestamp": start_time,
            "tag": "chat.invitation",
            "source": "visitor",
            "description": "A visitor asks who would like to look at a mysterious notebook.",
        }]
    else:
        # New conversations can wake via genuine external events; timers also
        # give each agent an independent opportunity to return from quiet work.
        initial_states = {
            name: {"mask": ["chat.", "action."], "timer_duration": "15m"}
            for name in names
        }
        initial_events = ([{
            "timestamp": start_time,
            "tag": "chat.allen",
            "source": "allen",
            "description": user_event[:700],
        }] if user_event.strip() else [])

    memory_bank = basic_associative_memory.AssociativeMemoryBank(
        sentence_embedder=embed, allow_duplicates=True,
    )
    master = interrupt_driven.GameMaster(
        entities=players,
        params={
            "name": "Room native Concordia referee",
            "start_time": start_time,
            "initial_events": initial_events,
            "initial_entity_states": {k: v for k, v in initial_states.items() if k in names},
        },
    ).build(model=model, memory_bank=memory_bank)

    if not type(master).__module__.startswith("concordia."):
        raise RuntimeError("Native Concordia game master is not active")
    engine = simultaneous.Simultaneous()
    records: list[dict[str, Any]] = []

    def record(step) -> None:
        records.append({
            "step": step.step,
            "acting": list(step.entity_actions),
            "actions": dict(step.entity_actions),
        })

    engine.run_loop(
        game_masters=[master],
        entities=players,
        max_steps=steps,
        step_callback=record,
    )
    scheduler = master.get_component("entity_scheduler")
    return {
        "framework": "google-deepmind/concordia",
        "engine_class": f"{type(engine).__module__}.{type(engine).__name__}",
        "game_master_class": f"{type(master).__module__}.{type(master).__name__}",
        "scheduler_class": f"{type(scheduler).__module__}.{type(scheduler).__name__}",
        "mode": mode,
        "players": names,
        "simulated_time": scheduler.format_time(),
        "steps": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("scripted", "llama"), required=True)
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--user-event", default="")
    parser.add_argument("--output", default="")
    parser.add_argument("--llama-url", default="http://127.0.0.1:18080/v1/chat/completions")
    args = parser.parse_args()
    if not 1 <= args.steps <= 100:
        parser.error("--steps must be between 1 and 100")
    report = run(
        mode=args.mode, steps=args.steps, user_event=args.user_event,
        llama_url=args.llama_url,
    )
    report_json = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(report_json, encoding="utf-8")
    print(report_json)


if __name__ == "__main__":
    main()
