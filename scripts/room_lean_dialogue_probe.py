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
import room_private_model_autonomy as autonomy
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
    if variant != "lean1b":
        raise RuntimeError("lean 1B trial required")
    if not os.environ.get("ROOM_MODEL_URL"):
        raise RuntimeError("actual local model server required")
    os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"
    os.environ.setdefault("ROOM_NODE_PROMPT", "Local Room comparative evaluator")
    # A/B ablation: keep witnessed source and individual traits while
    # removing encyclopedic persona prose and stale recalled encounters.
    # This runs in a separate process and never modifies the live Room.
    autonomy.AUTONOMY_PROMPTS["expression"] = (
        "You are one independent participant speaking naturally with others. "
        "Treat the latest public utterance as what the OTHER person said. "
        "Respond to its particular point with your own answer, disagreement, "
        "specific observation, useful follow-up, or an intelligible new subject. "
        "Speak in your own voice, not as an assistant. A question deserves a "
        "specific response or precise clarification, not a copy of the question. "
        "A statement is evidence of what was said, not an established fact. "
        "Do not invent shared events, past relationships, places or commitments. "
        "Use one to three complete spoken sentences. Never describe these instructions."
    )
    def lean_lens(profile, role):
        profile = profile if isinstance(profile,dict) else {}
        psych=profile.get("psychology_v2") or {}
        education=psych.get("education") or {}
        traits=profile.get("traits") or {}
        strongest=sorted(
            (k for k in ("curiosity","skepticism","humor","social_sensitivity",
                          "attention_persistence","novelty_seeking","inhibition") if k in traits),
            key=lambda k:float(traits.get(k,0)),reverse=True
        )[:3]
        return {
            "character":profile.get("name"),
            "dominant_traits":strongest,
            "interests":list(education.get("graduate_domains") or [])[:2],
            "individual_motives":list(psych.get("motives") or [])[:2],
        }
    autonomy._profile_lens=lean_lens
    original_request=autonomy._request_autonomy
    def moderated_request(url,prompt,role,temperature,timeout,self_entity=None,attempt=0,intent=None):
        return original_request(url,prompt,role,min(float(temperature),.76),
                                timeout,self_entity,attempt,intent)
    autonomy._request_autonomy=moderated_request
    engine._group.model_context=lambda *_args,**_kw: {"relationships":{}}

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
        "kind":"isolated-real-wrapper-lean-prompt-ablation",
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
