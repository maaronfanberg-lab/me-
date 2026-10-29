#!/usr/bin/env python3
"""Real Room wrapper and decoder A/B, one model per isolated GitHub runner.

No Room state, public conversation, or main branch changes are permitted.
The evaluation contains text for subsequent human review; exact-match and
word-count metrics are indicators, not evidence of genuine responsiveness.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import room_engine_v5 as engine
from room_conversational_floor import choose_next

NAMES = ("sarah", "mara", "owen", "jules")
CASES = (
    ("species didn't change into one shape", "owen"),
    ("What makes you think species might not change", "jules"),
    ("local forest ecosystem responds to species invasion", "mara"),
    ("not going to get what I want from our conversation", "sarah"),
)


def word_key(text):
    return " ".join(re.findall(r"[a-z0-9']+", str(text or "").lower()))


def source(feed, phrase):
    for item in reversed(feed.get("conversation") or []):
        if phrase.lower() in str(item.get("text") or "").lower():
            if item.get("speaker") in NAMES and item.get("id"):
                return {
                    "id": str(item["id"]),
                    "speaker": item["speaker"],
                    "text": str(item["text"]),
                }
    raise RuntimeError("Cannot ground public fixture: " + phrase)


def generate(previous, character, cfg, i):
    os.environ["ROOM_CYCLE_KEY"] = f"capacity-trial-20261029:{i}:{character}"
    os.environ["ROOM_FLOOR_REASON"] = ""
    os.environ["ROOM_FLOOR_SOURCE_ID"] = ""
    os.environ["ROOM_FLOOR_SPEAKER"] = ""
    profile = dict((cfg.get("p") or {}).get(character) or {})
    profile.setdefault("name", character.capitalize())
    psych = profile.get("psychology_v2") or {}
    pstate = {
        "who_i_am": str(psych.get("core_identity") or "I am a participant."),
        "what_i_want": "Understand what other people mean and contribute something real.",
    }
    payload = {
        "entity": character, "profile": profile, "private_self_state": pstate,
        "event": previous[-1], "context": previous[-3:], "topic": {},
        "keywords": [], "relationship": {},
        "partner": previous[-1]["speaker"], "mandatory_speech": True,
    }
    start = time.monotonic()
    try:
        response = engine._llama_model_run("expression", payload, timeout=70)
        elapsed = round(time.monotonic() - start, 3)
        if not isinstance(response, dict):
            return {"text": "", "elapsed_seconds": elapsed, "failure": "no_valid_expression"}
        return {
            "text": str(response.get("utterance") or "").strip(),
            "move": response.get("move"), "target": response.get("target"),
            "elapsed_seconds": elapsed,
        }
    except Exception as exc:
        return {"text": "", "elapsed_seconds": round(time.monotonic()-start,3),
                "failure": type(exc).__name__}


def main():
    variant = os.environ.get("ROOM_CAPACITY_VARIANT") or ""
    if variant != "qwen1p5":
        raise RuntimeError("Qwen 2.5 1.5B capacity trial only")
    if not os.environ.get("ROOM_MODEL_URL"):
        raise RuntimeError("actual local model server required")
    os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"
    os.environ.setdefault("ROOM_NODE_PROMPT", "Local Room comparative evaluator")
    feed = json.loads((ROOT / "room/feed.json").read_text())
    cfg = json.loads((ROOT / "room/config.json").read_text())
    cases = []
    for i, (phrase, selected) in enumerate(CASES):
        prior = source(feed, phrase)
        reply = generate([prior], selected, cfg, i)
        reply["full_source_echo"] = bool(
            reply.get("text") and word_key(reply["text"]) == word_key(prior["text"]))
        reply["words"] = len(word_key(reply.get("text")).split())
        cases.append({"source": prior, "speaker": selected, "response": reply})
        print(f"CASE {variant} {i+1}/{len(CASES)} "
              f"{prior['speaker']}->{selected}: {reply.get('text','')[:160]}", flush=True)
    # Start from the actual public species question, not a scripted exchange.
    history = [cases[0]["source"]]
    for n in range(5):
        choice = choose_next(history, {"recurrent": {}}, {"p": cfg.get("p") or {}},
                             {"entities": {person: {"people": {}} for person in NAMES}})
        selected = choice["speaker"]
        reply = generate(history, selected, cfg, 100+n)
        if not reply.get("text"):
            print("CHAIN FAILED", variant, n, reply.get("failure"), flush=True)
            break
        history.append({"id": f"capacity-{variant}-{n}", "speaker": selected,
                        "text": reply["text"], "elapsed_seconds": reply["elapsed_seconds"]})
        print("CHAIN", variant, n+1, selected, reply["text"][:180], flush=True)
    pairs = [(a, b) for a,b in zip(history, history[1:])]
    summary = {
        "model": variant,
        "cases": len(cases),
        "valid_replies": sum(bool(c["response"]["text"]) for c in cases),
        "whole_source_echoes": sum(c["response"]["full_source_echo"] for c in cases),
        "chain_generated_turns": len(history)-1,
        "chain_adjacent_whole_echoes": sum(
            word_key(a["text"]) == word_key(b["text"]) for a,b in pairs),
        "total_generation_seconds": round(
            sum(c["response"]["elapsed_seconds"] for c in cases)+
            sum(x.get("elapsed_seconds",0) for x in history[1:]),3),
    }
    outcome={
        "kind":"isolated-production-wrapper-Qwen2.5-1.5B-comparison",
        "variant":variant,
        "source_cycle":(feed.get("state") or {}).get("cycle"),
        "summary":summary,
        "cases":cases,
        "chain":history,
        "limitations":"Small fixed-seed sample; only human review of content can assess coherent action. Runtime must be checked separately.",
    }
    path=ROOT / f"docs/research/room-capacity-{variant}-20261029.json"
    path.write_text(json.dumps(outcome,ensure_ascii=False,indent=2)+"\n")
    print("SUMMARY",variant,json.dumps(summary),flush=True)


if __name__=="__main__":
    main()
