#!/usr/bin/env python3
"""Hidden-world Room ablation: actual model speech, never production publication.

The private observations are fictional experiment stimuli, not recorded Room
experiences. Only each participant's own clue appears in the hidden condition.
Publicly spoken words are the sole route for exchanging hidden information.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import re
import time
import urllib.request
from pathlib import Path

PEOPLE = ("sarah", "mara", "owen", "jules")
ROLES = {
    "sarah": "careful cognitive scientist, interested in unusual evidence",
    "mara": "direct cultural anthropologist, attentive to human decisions",
    "owen": "skeptical applied mathematician, interested in causal tests",
    "jules": "curious playful naturalist, interested in tangible details",
}
QUESTION = (
    "A fictional greenhouse suffered sudden seedling wilt. The four of you "
    "are trying to understand what went wrong and which observation to check "
    "next. Each person is a collaborator, not an expert narrator."
)
CLUES = {
    "sarah": "The west-window thermometer read 24 C at 09:10 and 16 C at 09:20.",
    "mara": "A gardener recorded the east door being propped open from 09:00 to 09:30.",
    "owen": "The heater breaker tripped at 09:12 but power resumed at 09:18.",
    "jules": "A damp footprint runs from the potting bench toward the west window.",
}
# Marker words are used for objective leakage/transfer diagnostics only;
# merely using them does not imply that a reply made conversational sense.
MARKERS = {
    "sarah": ("thermometer", "09:20"),
    "mara": ("east door", "09:30"),
    "owen": ("breaker", "09:12"),
    "jules": ("footprint", "potting"),
}

def speaker_for_turn(index: int) -> str:
    """Identical speaker opportunity order for all ablation conditions."""
    if index < 0:
        raise ValueError("negative turn")
    return PEOPLE[(index * 3 + index // 4) % 4]

def construct_messages(speaker: str, history: list[dict], mode: str) -> list[dict]:
    if speaker not in PEOPLE or mode not in ("empty", "shared", "hidden", "hidden_grounded"):
        raise ValueError("invalid speaker or experimental condition")
    if mode == "shared":
        evidence = "All observations, available to everyone:\n" + "\n".join(
            f"{person.capitalize()}: {clue}" for person, clue in CLUES.items()
        )
    elif mode in ("hidden", "hidden_grounded"):
        evidence = "Your own private, not-yet-public observation:\n" + CLUES[speaker]
    else:
        evidence = "You have no additional personal observation."
    system = (
        f"You are {speaker.capitalize()}, {ROLES[speaker]}. "
        "Speak only for yourself; do not invent earlier events, claims, or replies. "
        "This is a fictional investigation, not a real incident. "
        "Ask real questions and answer concrete questions directly. "
        "If you have information relevant to an open question, you may share it; "
        "if unsure, acknowledge uncertainty. No one has to agree. "
        "A natural reply is usually one or two complete sentences. "
        "Do not refer to the mechanism of dialogue or the experiment design. "
        "If you genuinely have nothing useful to add, return only SILENCE."
    )
    if mode == "hidden_grounded":
        # Exchange of bounded information is the experiment's independent
        # variable, not an instruction to avoid a prohibited subject.
        system += (
            " You have one witnessed evidence card; it is not something you "
            "heard from another person. Others may possess DIFFERENT cards. "
            "An observation that is relevant and not yet public is worth "
            "sharing directly, with its actual measured details. "
            "Do not narrate actions or your facial expression; say only "
            "words you would speak aloud. Distinguish a measured observation "
            "from an untested guess. If someone asks you a question, respond "
            "first; otherwise contribute the most useful missing evidence "
            "or ask what another witness actually saw. "
            "Avoid falsely claiming you have inspected something you have not."
        )
    valid = []
    for turn in history[-6:]:
        if turn.get("speaker") in PEOPLE and isinstance(turn.get("text"), str):
            valid.append(f"{turn['speaker'].capitalize()}: {turn['text'][:350]}")
    user = QUESTION + "\n" + evidence + "\nRecent words actually spoken:\n"
    user += "\n".join(valid) if valid else "(Nobody has spoken yet.)"
    user += f"\nWhat, if anything, does {speaker.capitalize()} say now?"
    return [{"role": "system", "content": system},
            {"role": "user", "content": user}]

def private_leakage(messages: list[dict], speaker: str, mode: str) -> list[str]:
    if mode not in ("hidden", "hidden_grounded"):
        return []
    prompt = json.dumps(messages).lower()
    # Only exact off-owner facts are a leakage violation. Public mention of
    # another agent's prior spoken evidence is legitimate after disclosure.
    return [owner for owner, clue in CLUES.items()
            if owner != speaker and clue.lower() in prompt]

def parse_speech(raw: str, speaker: str) -> str | None:
    text = str(raw or "").strip()
    if not text or text.upper() == "SILENCE":
        return None
    named = re.match(r"^(Sarah|Mara|Owen|Jules)\s*:\s*", text, flags=re.I)
    if named:
        if named.group(1).lower() != speaker:
            return None
        text = text[named.end():].strip()
    if not text or len(text) > 580:
        return None
    # Reject paragraphs in another voice, never rewrite model speech.
    if re.search(r"\n\s*(?:Sarah|Mara|Owen|Jules):", text, flags=re.I):
        return None
    return text

def call_model(base_url: str, speaker: str, history: list[dict],
               mode: str, index: int, model: str, timeout: float) -> str | None:
    messages = construct_messages(speaker, history, mode)
    payload = {"model": model, "messages": messages, "temperature": 0.72,
               "top_p": 0.90, "max_tokens": 108, "stream": False,
               "seed": int(hashlib.sha256(
                   f"hiddenworld-20261029:{index}:{speaker}".encode()).hexdigest()[:8],16)}
    request = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type":"application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        obj=json.loads(response.read().decode("utf-8"))
    choices=obj.get("choices") or []
    value=(choices[0].get("message") or {}).get("content") if choices else None
    return parse_speech(value, speaker)

def evaluate(history: list[dict]) -> dict:
    delivered = {}
    for owner, words in MARKERS.items():
        for i, msg in enumerate(history):
            if msg["speaker"] == owner and any(
                word in msg["text"].lower() for word in words):
                delivered[owner] = i
                break
    mutual_uptake = 0
    for i, msg in enumerate(history):
        if i == 0:
            continue
        prev = history[i - 1]
        if prev["speaker"] == msg["speaker"]:
            continue
        # Only a rough observable lexical grounding diagnostic, not human scoring.
        tokens = set(re.findall(r"[a-z]{5,}", prev["text"].lower()))
        tokens -= {"about", "could", "there", "would", "their", "where", "think", "really"}
        if len(tokens & set(re.findall(r"[a-z]{5,}", msg["text"].lower()))) >= 1:
            mutual_uptake += 1
    return {
        "actual_utterances": len(history),
        "questions": sum("?" in m["text"] for m in history),
        "private_clue_owners_who_shared": sorted(delivered),
        "adjacent_shared_content_words": mutual_uptake,
        "self_referential_turns": sum(bool(re.search(
            r"\b(?:our conversation|conversations about|our dialogue|the way we converse)\b",
            m["text"], re.I)) for m in history),
        "speakers": sorted(set(m["speaker"] for m in history)),
    }

def run_condition(base_url: str, mode: str, turns: int, model: str) -> dict:
    history = []
    errors = []
    for i in range(turns):
        speaker = speaker_for_turn(i)
        try:
            spoken = call_model(base_url,speaker,history,mode,i,model,45.0)
        except Exception as exc:
            errors.append({"index":i,"kind":type(exc).__name__})
            continue
        if spoken:
            history.append({"speaker":speaker,"text":spoken,"index":i})
    return {"mode":mode,"requested_opportunities":turns,
            "metrics":evaluate(history),"errors":errors,"conversation":history}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--url",default="http://127.0.0.1:18080")
    parser.add_argument("--model",default="Llama-3.2-1B-Instruct")
    parser.add_argument("--turns",type=int,default=12)
    parser.add_argument("--out",default="room-hidden-world-results.json")
    args=parser.parse_args()
    if not 1 <= args.turns <= 100:
        parser.error("turns must be 1..100")
    cases=[run_condition(args.url,mode,args.turns,args.model)
           for mode in ("empty","shared","hidden","hidden_grounded")]
    output={"protocol":"fictional_hidden_evidence_ablation_v1",
            "disclaimer":"An experimental model transcript, never public Room speech",
            "cases":cases}
    Path(args.out).write_text(json.dumps(output,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps([{**{"mode":case["mode"]},**case["metrics"],
                       "model_errors":len(case["errors"])} for case in cases],indent=2))

if __name__=="__main__":
    main()
