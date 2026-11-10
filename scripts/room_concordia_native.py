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
from concordia.components.game_master import interrupt_scheduling
from concordia.components.game_master import interrupt_response_parsing
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
        "Values: " + "; ".join(map(str, (psyche.get("values") or [])[:5])),
        "What catches my interest: " + "; ".join(
            map(str, (psyche.get("attention_magnets") or [])[:5])
        ),
        "Pursue your own substantive interests rather than discussing the "
        "design, quality or mechanics of conversation. You may volunteer a "
        "concrete observation, pursue an idea, act, or stay occupied quietly.",
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
        action, data = interrupt_response_parsing.extract_json_block(output)
        safe_silence = '\n{"mask": [], "timer": {"time": "15m", "reason": "reflect quietly"}}'
        if not isinstance(data.get("mask"), list) or not isinstance(data.get("timer"), dict):
            return safe_silence
        if any(not isinstance(v, str) for v in data["mask"]):
            return safe_silence
        if not (data["timer"].get("time") or data["timer"].get("until")):
            return safe_silence
        if len(action) > 520 or re.search(
            r"(?i)system prompt|hidden prompt|developer message|chain of thought|room_prompt_",
            action,
        ):
            return safe_silence
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
        match = re.findall(r"What does (Sarah|Mara|Owen|Jules) (?:independently choose to )?do next", prompt)
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
        work = (', "work": {"verb":"inspect","object":"notebook",'
                '"goal":"Learn what the notebook actually contains"}'
                if name == "Jules" else "")
        return (action + '\n{"mask": [], "timer": '
                '{"time": "45m", "reason": "resume own work"}' + work + '}')


def build_agents(model: language_model.LanguageModel, config: Mapping[str, Any],
                 world_contexts: Mapping[str, str] | None = None):
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
            "world": agent_components.constant.Constant(
                state=str((world_contexts or {}).get(name, ""))[:3000],
                pre_act_label="Verified world and personal current work",
            ),
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
                history_length=8,
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


def scheduler_is_exhausted(state: Mapping[str, Any]) -> bool:
    """The native scheduler can reach a terminal all-silent state.

    A valid empty subscription mask plus no timers or future events is
    voluntary quiet, but it must not kill the *service*. Keep the characters'
    memory and let them resume independent activity in a fresh scheduling
    interval, without generating or requiring any public utterance.
    """
    if not isinstance(state, Mapping):
        return False
    masks = state.get("masks")
    timers = state.get("timers")
    if not isinstance(masks, dict) or not masks:
        return False
    if not isinstance(timers, dict) or not timers:
        return False
    return (
        all(not any(str(tag).strip() for tag in (mask or []))
            for mask in masks.values())
        and all(not timer for timer in timers.values())
        and not state.get("event_queue")
    )


def run(
    *,
    mode: str,
    steps: int = 5,
    root: Path = ROOT,
    start_time: str = "2026-11-09T09:00:00",
    user_event: str = "",
    bootstrap_context: Sequence[Mapping[str, str]] = (),
    recent_public: Sequence[Mapping[str, str]] = (),
    world_contexts: Mapping[str, str] | None = None,
    world_events: Sequence[Mapping[str, str]] = (),
    llama_url: str = "http://127.0.0.1:18080/v1/chat/completions",
    state_in: Path | None = None,
    state_out: Path | None = None,
) -> dict[str, Any]:
    config = json.loads((root / "room" / "config.json").read_text(encoding="utf-8"))
    model = (
        ScriptedModel()
        if mode == "scripted"
        else LocalLlama(llama_url, os.getenv("ROOM_CHAT_MODEL_ID", "Llama-3.2-3B-Instruct"))
    )
    players = build_agents(model, config, world_contexts=world_contexts)
    names = [p.name for p in players]
    # One-time migration of publicly witnessed Room interactions only.
    if state_in is None:
        for item in list(bootstrap_context)[-12:]:
            speaker = str(item.get("speaker") or "").strip().lower()
            utterance = str(item.get("text") or "").strip()[:520]
            if speaker in (*PARTICIPANTS, "allen") and utterance:
                for player in players:
                    if player.name.lower() != speaker:
                        player.observe(f"{speaker.capitalize()}: {utterance}")

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
        # Stagger wake-ups: no compulsory synchronized four-character beat.
        delays = {"Sarah": "7m", "Mara": "19m", "Owen": "31m", "Jules": "43m"}
        initial_states = {
            name: {"mask": ["chat.allen", "action."],
                   "timer_duration": delays[name],
                   "timer_description": "return to own interests"}
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
            "call_to_action": (
                "What does {name} independently choose to do next? Respect your "
                "own enduring goal and only the VERIFIED physical outcomes in "
                "your context. You may work privately, listen, rest, or speak "
                "only when you have a specific observation or consequence to "
                "respond to. Do not talk about the mechanics or quality of "
                "conversation. Do not announce plans as accomplished results. "
                "The action text before the JSON is ONLY what you actually "
                "say or physically do now, written in first person. It may be "
                "empty when you work privately or remain quiet. End with ONE "
                "JSON control object containing mask (a list of event prefixes) "
                "and timer (a time duration and personal reason). A valid "
                "minimal control object looks like "
                "{\"mask\":[\"chat.allen\",\"action.\"],"
                "\"timer\":{\"time\":\"15m\",\"reason\":\"review my work\"}}. "
                "The optional work field is an object whose two required keys are verb "
                "and object, with values you select from your current world "
                "affordances. No sample task, goal, or dialogue is prescribed. "
                "Never copy generic placeholder goals: retain your existing "
                "real personal goal unless you have a genuinely specific "
                "new one. The world referee, not you, determines whether a "
                "work action is actually completed. "
                "Use [] for mask when focusing on your own work. Timers are "
                "about personal attention, NEVER compulsory conversation. "
                "Never invent another character's speech or actions."
            ),
        },
    ).build(model=model, memory_bank=memory_bank)

    if not type(master).__module__.startswith("concordia."):
        raise RuntimeError("Native Concordia game master is not active")
    scheduler = master.get_component("entity_scheduler")
    if state_in is not None:
        snapshot = json.loads(Path(state_in).read_text(encoding="utf-8"))
        if snapshot.get("schema") != 1 or snapshot.get("players") != names:
            raise ValueError("Native Concordia checkpoint incompatible with these players")
        saved_scheduler = snapshot["game_master"]["context_components"]["entity_scheduler"]
        if scheduler_is_exhausted(saved_scheduler):
            # The upstream scheduler otherwise returns [''] as an actor and
            # Simultaneous raises ValueError. Preserve every character's
            # memory and the GM's history; refresh ONLY its exhausted
            # scheduling interval. This creates opportunities, not dialogue.
            print("Native Concordia scheduler exhausted; rearming quiet "
                  "independent timers without resetting character memory",
                  flush=True)
            snapshot["game_master"]["context_components"]["entity_scheduler"] = scheduler.get_state()
            saved_scheduler = scheduler.get_state()
        master.set_state(snapshot["game_master"])
        for player in players:
            player.set_state(snapshot["entities"][player.name])
            # Avoid letting the last 24 repetitive utterances swamp every
            # new goal and environmental observation.
            player.get_component("observations").set_state({"history_length": 8})
            # World context comes from the actual committed environment,
            # never from the earlier checkpoint's obsolete constant.
            player.get_component("world").set_state({
                "state": str((world_contexts or {}).get(player.name.lower(), ""))[:3000]
            })
        if scheduler.get_state() != saved_scheduler:
            raise ValueError("Concordia scheduler checkpoint was not restored")
        if user_event.strip():
            scheduler.inject_event(interrupt_scheduling.Event(
                timestamp=scheduler.get_current_time(), tag="chat.allen",
                source="allen", description=user_event[:700],
            ))
    # Physical consequences are actual native Concordia interrupts. Other
    # agents may notice them without anyone being instructed to speak.
    # Use the existing action.* subscription so persisted agent attention
    # masks keep working; the source explicitly identifies the environment.
    injected_world_events = []
    for event in list(world_events)[-8:]:
        event_id = str(event.get("id") or "")
        kind = str(event.get("kind") or "")
        actor = str(event.get("actor") or "").lower()
        description = str(event.get("description") or "").strip()
        if (not event_id.startswith("life-") or kind not in
                {"work_started", "work_completed"} or actor not in PARTICIPANTS
                or not description or len(description) > 280):
            continue
        scheduler.inject_event(interrupt_scheduling.Event(
            timestamp=scheduler.get_current_time(),
            tag="action.environment",
            source="room_environment",
            description=f"Verified event [{event_id}]: {description}",
        ))
        injected_world_events.append(event_id)
    # Give every agent the same genuinely witnessed public evidence. Native
    # Concordia memory persists in the checkpoint; the caller supplies only
    # turns not previously observed, so this does not re-prime stale loops.
    for item in list(recent_public)[-8:]:
        speaker = str(item.get("speaker") or "").strip().lower()
        utterance = str(item.get("text") or "").strip()[:520]
        if speaker in (*PARTICIPANTS, "allen") and utterance:
            for player in players:
                if player.name.lower() != speaker:
                    player.observe(f"Publicly witnessed: {speaker.capitalize()} said: {utterance}")
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
    if state_out is not None:
        # This is Concordia's own serialized entity, memory and GM state.
        # Atomic persistence so an interrupted write cannot corrupt a snapshot.
        snapshot = {
            "schema": 1,
            "framework": "google-deepmind/concordia",
            "players": names,
            "game_master": master.get_state(),
            "entities": {p.name: p.get_state() for p in players},
        }
        destination = Path(state_out)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_name(destination.name + ".tmp")
        temp.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, destination)
    return {
        "framework": "google-deepmind/concordia",
        "engine_class": f"{type(engine).__module__}.{type(engine).__name__}",
        "game_master_class": f"{type(master).__module__}.{type(master).__name__}",
        "scheduler_class": f"{type(scheduler).__module__}.{type(scheduler).__name__}",
        "mode": mode,
        "injected_world_events": injected_world_events,
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
    parser.add_argument("--state-in", default="")
    parser.add_argument("--state-out", default="")
    parser.add_argument("--llama-url", default="http://127.0.0.1:18080/v1/chat/completions")
    args = parser.parse_args()
    if not 1 <= args.steps <= 100:
        parser.error("--steps must be between 1 and 100")
    report = run(
        mode=args.mode, steps=args.steps, user_event=args.user_event,
        llama_url=args.llama_url,
        state_in=Path(args.state_in) if args.state_in else None,
        state_out=Path(args.state_out) if args.state_out else None,
    )
    report_json = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(report_json, encoding="utf-8")
    print(report_json)


if __name__ == "__main__":
    main()
