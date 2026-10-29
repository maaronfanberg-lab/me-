#!/usr/bin/env python3
"""Production Room local speech-first Llama adapter.

Only the real local model speaks. Structured metadata is inferred conservatively
from public speech, for continuity with the unchanged preflight and publication
gates. No synthetic speech, model fallback lines, or saved memory mutations.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.parse
import urllib.request

from room_conversational_floor import audible_addressee, ORDER
from room_research_architecture import autonomous_text_issue
from room_social_v5 import words as social_words

PARTICIPANTS=(*ORDER,"allen")
ALLOWED_MOVES={"answer","deepen","disclose","compare","disagree","repair",
               "support","callback","bridge","close"}
SPEAKER_PREFIX=re.compile(r"^(?:Sarah|Mara|Owen|Jules)\s*:\s*",re.I)


def chat_endpoint(model_url: str) -> str:
    parsed=urllib.parse.urlsplit(str(model_url or "").strip())
    if parsed.scheme!="http" or parsed.hostname not in {"127.0.0.1","localhost","::1"}:
        raise ValueError("Room speech-first model must be a local HTTP model server")
    return urllib.parse.urlunsplit(
        (parsed.scheme,parsed.netloc,"/v1/chat/completions","",""))


def witnessed_context(payload: dict, entity: str) -> list[dict]:
    presence=payload.get("room_presence") or {}
    present=set(presence.get("present") or PARTICIPANTS)
    source=list(payload.get("context") or [])
    event=payload.get("event")
    if isinstance(event,dict) and event.get("id") not in {
            s.get("id") for s in source if isinstance(s,dict)}:
        source.append(event)
    out=[]
    for item in source:
        if not isinstance(item,dict) or item.get("speaker") not in present:
            continue
        speaker=str(item.get("speaker") or "").strip().lower()
        spoken=str(item.get("text") or "").strip()
        if speaker not in PARTICIPANTS or not spoken:
            continue
        out.append({"speaker":speaker,"text":spoken[:520],"id":item.get("id")})
    return out[-3:]


def messages(payload: dict, entity: str) -> list[dict]:
    profile=payload.get("profile") or {}
    psych=profile.get("psychology_v2") or {}
    persona=str(psych.get("core_identity") or "A curious and independent participant.")[:300]
    interests=[str(x)[:100] for x in (psych.get("motives") or [])[:2]]
    presence=payload.get("room_presence") or {}
    present=[x.capitalize() for x in PARTICIPANTS if
             x in set(presence.get("present") or PARTICIPANTS)]
    system=(
        f"You are {entity.capitalize()}, a distinct person in a conversation "
        f"with {', '.join(present)}. Identity: {persona}. "
        f"Your personal interests: {'; '.join(interests)}. "
        "Speak directly to the other people, naturally and in your own words. "
        "Respond to what the last person actually meant where useful. "
        "You can agree, disagree, clarify, add a concrete example, or introduce your own relevant idea. "
        "Do not simply repeat their words or invent previous events or relationships. "
        "Your response is one or two complete spoken sentences, not an explanation of your job."
    )
    history=witnessed_context(payload,entity)
    transcript="\n".join(
        f"{h['speaker'].capitalize()}: {h['text']}" for h in history
    )
    last=("Latest public Room turns:\n"+transcript if history
          else "Nobody has spoken to you directly in this moment.")
    user=last+f"\n\nNow speak as {entity.capitalize()}. Say only your own next conversational turn."
    return [{"role":"system","content":system},{"role":"user","content":user}]


def speech_metadata(text: str, payload: dict, entity: str) -> dict:
    history=witnessed_context(payload,entity)
    source=history[-1] if history else {}
    present=set((payload.get("room_presence") or {}).get("present") or PARTICIPANTS)
    spoken_target=audible_addressee(entity,text,tuple(x for x in ORDER if x in present))
    nominated=str(payload.get("partner") or "").strip().lower()
    prior=str(source.get("speaker") or "").strip().lower()
    target=next((p for p in (spoken_target,prior,nominated)
                 if p in present and p != entity and p in PARTICIPANTS),None)
    if target is None:
        target=next((p for p in ORDER if p in present and p != entity),None)
    if target is None:
        raise ValueError("no available conversational partner")
    deliberation=payload.get("deliberation")
    proposed=str((deliberation or {}).get("action") or "").lower() if isinstance(deliberation,dict) else ""
    # A naturally addressed disagreement can start with a vocative.
    stance_text = re.sub(r"^\s*(?:Sarah|Mara|Owen|Jules)\s*[:,]\s*",
                         "", text, flags=re.I)
    if proposed in ALLOWED_MOVES:
        move=proposed
    elif re.match(r"^\s*(?:no[,!. ]|i\s+disagree\b|i\s+don't\s+agree\b)",
                  stance_text,re.I):
        move="disagree"
    elif source and str(source.get("text") or "").rstrip().endswith("?"):
        move="repair" if text.endswith("?") else "answer"
    else:
        move="deepen"
    terms=[w for w in social_words(text) if w not in PARTICIPANTS][:4]
    return {"decision":"SPEAK","utterance":text,"move":move,
            "target":target,"semantic_terms":terms or ["speech"]}


def run(payload: dict, timeout: int = 45) -> dict | None:
    entity=str(payload.get("entity") or "").strip().lower()
    if entity not in ORDER:
        raise ValueError("unexpected autonomous Room entity")
    url=chat_endpoint(os.environ.get("ROOM_MODEL_URL") or "")
    incoming=messages(payload,entity)
    cycle_key=str(os.environ.get("ROOM_CYCLE_KEY") or "room-speech-beat")
    for attempt in range(2):
        keyed=f"{cycle_key}:chat-speech:{entity}:{attempt}"
        seed=int(hashlib.sha256(keyed.encode()).hexdigest()[:8],16) & 0x7FFFFFFF
        prompt=json.loads(json.dumps(incoming))
        if attempt:
            prompt[0]["content"] += (
                " The previous candidate did not pass speech safety or completeness checks. "
                "Use a complete, natural first-person response in your own words.")
        body={"model":"Llama-3.2-1B-Instruct","messages":prompt,
              "temperature":.78,"top_p":.93,
              "max_tokens":145,"seed":seed,"stream":False}
        req=urllib.request.Request(
            url, data=json.dumps(body,ensure_ascii=False).encode(),
            headers={"Content-Type":"application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req,timeout=max(1,int(timeout))) as response:
                raw=json.loads(response.read().decode("utf-8","replace"))
            choices=raw.get("choices") or []
            data=choices[0].get("message") or {} if choices else {}
            spoken=SPEAKER_PREFIX.sub("",str(data.get("content") or "").strip()).strip()
            if not spoken or len(spoken)>700:
                continue
            if autonomous_text_issue({"speaker":entity,"text":spoken}):
                continue
            from room_private_model import _contains_explicit_leak_marker, _contains_meta_language
            if _contains_explicit_leak_marker(spoken) or _contains_meta_language(spoken):
                continue
            return speech_metadata(spoken,payload,entity)
        except (TimeoutError,urllib.error.URLError,ValueError,KeyError,TypeError,IndexError) as exc:
            print(f"Room chat speech local generation attempt {attempt+1} failed for {entity}: {type(exc).__name__}")
            continue
    print(f"Room chat speech quarantined {entity}: no acceptable local model response")
    return None
