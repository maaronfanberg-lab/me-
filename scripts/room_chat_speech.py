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
from pathlib import Path

from room_conversational_floor import audible_addressee, ORDER
from room_research_architecture import autonomous_text_issue
from room_social_v5 import words as social_words

PARTICIPANTS=(*ORDER,"allen")
ALLOWED_MOVES={"answer","deepen","disclose","compare","disagree","repair",
               "support","callback","bridge","close"}
SPEAKER_PREFIX=re.compile(r'^\s*["“]?\s*(Sarah|Mara|Owen|Jules|Allen)\s*:\s*',re.I)


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
        # Allen's accepted public text is user-authored, never silently
        # shortened to the same 520-char budget used for autonomous speech.
        limit=700 if speaker=="allen" else 520
        out.append({"speaker":speaker,"text":spoken[:limit],"id":item.get("id")})
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
        "When someone asks a question or requests help, engage with what they actually asked; "
        "if necessary details are missing, ask instead of inventing their request. "
        "Do not assign an unstated subject, motive, or prior event to another speaker. "
        "You may disagree, decline, or redirect for a concrete reason. "
        "You can agree, disagree, clarify, add a concrete example, or introduce your own relevant idea. "
        "Do not simply repeat their words or invent previous events or relationships. "
        "Give a complete, natural conversational turn, usually one or two sentences and under 40 words. End with punctuation. " 
        "Do not address yourself by name or present imagined past events as facts. " 
        "This is spoken conversation, not an explanation of your job."
    )
    history=witnessed_context(payload,entity)
    transcript="\n".join(
        f"{h['speaker'].capitalize()}: {h['text']}" for h in history
    )
    last=("Latest public Room turns:\n"+transcript if history
          else "Nobody has spoken to you directly in this moment.")
    new_world_event = None
    situational_grounding = ''
    # Experiment-only: person-specific, *non-omniscient* fictional observations.
    # This must never pre-empt a real visitor's message. Default remains off.
    if os.environ.get("ROOM_HIDDEN_WORLD_EXPERIMENT") == "1" and not (
        history and history[-1]["speaker"] == "allen"
    ):
        from room_hidden_world import context_for, trial_active, event_at, scene_for_cycle, private_observation, situational_notice, followup_active
        room_cycle = payload.get("room_cycle")
        if room_cycle is None:
            state_path = Path(__file__).resolve().parents[1] / "room" / "state.json"
            room_cycle = json.loads(state_path.read_text()).get("cycle", 0)
        if trial_active(int(room_cycle)):
            system += chr(10) + context_for(entity, int(room_cycle))
            if followup_active(int(room_cycle)):
                system += (
                    " You are a participant physically present in this fictional scene. "
                    "People can compare observations and try specific actions; the scene "
                    "may react to witnessed actions. Explain what you see or try in plain "
                    "language, rather than turning a practical difficulty into a lecture. "
                    "You can also disagree, ask for an observation, or pursue a real "
                    "interlocutor's more important question."
                )
            situational_grounding = situational_notice(entity, int(room_cycle))
            if event_at(int(room_cycle)):
                new_world_event = (scene_for_cycle(int(room_cycle)).common,
                                   private_observation(entity, int(room_cycle)))
    user=(last+"\n\nThe final transcript line is the most recent real public turn. "
          "Use its meaning, not a copy of its wording, as your starting point. "
          f"Now speak as {entity.capitalize()}. Say only your own next conversational turn.")
    if new_world_event:
        shared, own = new_world_event
        user = (
            last
            + chr(10) + chr(10)
            + "A new environmental event just occurred in your fictional shared setting, AFTER the latest public turn: "
            + shared
            + " You personally noticed: " + own
            + " No one else knows your observation unless you tell them. "
              "Speak naturally as yourself; you may react to the event, ask another person, "
              "or continue an urgent earlier exchange. Say only your own next turn."
        )
    # Explicitly separate witnessed character action and fictional environment
    # consequence from ordinary speech. No synthetic speech is generated.
    if (situational_grounding and os.environ.get("ROOM_WORLD_ACTIONS") == "1"
            and history and (35220 <= int(room_cycle) < 35232
                         or followup_active(int(room_cycle)))):
        from room_hidden_world import scene_for_cycle
        from room_world_actions import action_consequence
        witnessed = history[-1]
        effect = action_consequence(
            scene_for_cycle(int(room_cycle)).identifier,
            witnessed.get("speaker"),
            witnessed.get("text"),
        )
        if effect:
            user += (chr(10) + chr(10)
                     + "SIMULATED ENVIRONMENT RESPONSE TO THE PREVIOUS WITNESSED ACTION: "
                     + effect["effect"]
                     + " This observation is now visible to the group, but it is not "
                       "another participant speaking and does not prove anyone has "
                       "understood it. You can react or ask about it, naturally.")
    # Use actual, source-bearing public observations as collective memory in
    # the second 12-turn replication phase. A scene card by itself is private
    # and never appears in this ledger until its owner actually speaks it.
    if (situational_grounding
            and os.environ.get("ROOM_SCENE_PUBLIC_LEDGER") == "1"
            and int(room_cycle) >= 35280):
        from room_hidden_world import scene_common_ground
        try:
            published_file = Path(__file__).resolve().parents[1] / "room" / "feed.json"
            published_history = json.loads(published_file.read_text()).get("conversation") or []
            public_knowledge = scene_common_ground(int(room_cycle), published_history)
        except (OSError, ValueError, TypeError):
            public_knowledge = ""
        if public_knowledge:
            user += chr(10) + chr(10) + public_knowledge
    # Finite second-scene source-linked intention recall. This retains spoken
    # plans as *unfulfilled* until that same actor publicly reports acting.
    # No generated substitute actions, speaker coercion or mandatory reply.
    if (situational_grounding and os.environ.get("ROOM_PLAN_FOLLOWTHROUGH") == "1"
            and not (history and history[-1]["speaker"] == "allen")):
        from room_followthrough import notice as plan_notice, active as plan_active
        try:
            if plan_active(int(room_cycle)):
                source = json.loads((Path(__file__).resolve().parents[1]
                                     / "room" / "feed.json").read_text())
                public = source.get("conversation") or []
                if isinstance(public, list):
                    outstanding = plan_notice(int(room_cycle), public, entity=entity)
                    if outstanding:
                        user += "\n\n" + outstanding
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if situational_grounding:
        # World evidence is a distinct channel, not an invented speaker turn.
        # Its final placement prevents short abstract transcript tails from
        # silently erasing the ongoing situation during this bounded window.
        user += chr(10) + chr(10) + situational_grounding
        if followup_active(int(room_cycle)):
            from room_world_actions import available_actions
            from room_hidden_world import scene_action_ledger
            completed = set()
            # Only observed, identified PUBLIC actions remove a suggested check.
            # Private clue cards and promises are never accepted as completion.
            try:
                scene_public = json.loads((Path(__file__).resolve().parents[1]
                                           / "room" / "feed.json").read_text()).get("conversation") or []
                completed = {(e["action"], e["object"])
                             for e in scene_action_ledger(int(room_cycle), scene_public)}
            except (OSError, ValueError, KeyError, TypeError):
                pass
            possibilities = available_actions(
                scene_for_cycle(int(room_cycle)).identifier,
                completed=completed)
            if possibilities:
                user += (
                    chr(10) + chr(10)
                    + "PHYSICAL OPTIONS IN THE FICTIONAL SETTING (not actions anyone "
                      "has yet taken, and not dialogue you must imitate): "
                    + "; ".join(possibilities)
                    + ". You can speak naturally, decline, or change course. "
                      "In this fictional environment an action happens when you "
                      "describe yourself doing it now ('I inspect the filter'), "
                      "and the next speaker can see the outcome. Saying you "
                      "intend to inspect later ('I'll inspect') records a plan "
                      "but does not make the inspection happen. Use no other "
                      "person's unspoken observation as your own."
                )
    # Source-linked causal environment. No invented speaker utterances.
    # An actual visitor turn supersedes the fictional setting.
    if (os.environ.get("ROOM_CAUSAL_WORLD_EXPERIMENT") == "1"
            and not (history and history[-1]["speaker"] == "allen")):
        from room_causal_world import active as causal_active, cue_for
        try:
            source_cycle = payload.get("room_cycle")
            if source_cycle is None:
                source_cycle = json.loads((Path(__file__).resolve().parents[1]
                                          / "room" / "state.json").read_text())["cycle"]
            source_cycle = int(source_cycle)
            if causal_active(source_cycle):
                source = json.loads((Path(__file__).resolve().parents[1]
                                     / "room" / "feed.json").read_text())
                public = source.get("conversation") or []
                if isinstance(public, list):
                    notice = cue_for(entity, source_cycle, public)
                    if notice:
                        user += "\n\n" + notice
        except (OSError, ValueError, KeyError, TypeError):
            pass  # malformed data never creates fictitious shared evidence
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


def unfinished_model_quotation(spoken: str) -> bool:
    """An unclosed model-authored quotation is not a complete public turn."""
    text = str(spoken or "")
    return (text.count('"') % 2 != 0 or text.count("“") > text.count("”"))


def complete_model_prefix(spoken: str) -> str:
    """Use only a complete, self-standing prefix actually authored by the model.

    This is *not* generated replacement text or a word-list filter. Reject
    incomplete fragments, contrary follow-ons, and previews with no substantive
    complete action. The normal publication validation still decides acceptance.
    """
    text = str(spoken or "").strip()
    options = []
    for found in re.finditer(r'[.!?](?=(?:["”’]?\s+|$))', text):
        end = found.end()
        if end < len(text) and text[end] in "\"”’":
            end += 1
        prefix = text[:end].strip()
        count = len(re.findall(r"[a-z0-9']+", prefix.casefold()))
        if 9 <= count <= 34 and prefix not in options:
            options.append(prefix)
    for prefix in reversed(options):
        remaining = text[len(prefix):].strip().lstrip("\"'”’").strip().casefold()
        # Do not take a sentence out of a statement that is about to
        # reverse or qualify it, even if the continuation was truncated.
        if re.match(r"^(?:but|however|actually|except|although|instead|yet|nevertheless|no|on the other hand|on the contrary)\b",
                    remaining):
            continue
        return prefix
    return ""


def run(payload: dict, timeout: int = 45) -> dict | None:
    entity=str(payload.get("entity") or "").strip().lower()
    if entity not in ORDER:
        raise ValueError("unexpected autonomous Room entity")
    url=chat_endpoint(os.environ.get("ROOM_MODEL_URL") or "")
    incoming=messages(payload,entity)
    cycle_key=str(os.environ.get("ROOM_CYCLE_KEY") or "room-speech-beat")
    last_failure=""
    for attempt in range(3):
        keyed=f"{cycle_key}:chat-speech:{entity}:{attempt}"
        seed=int(hashlib.sha256(keyed.encode()).hexdigest()[:8],16) & 0x7FFFFFFF
        prompt=json.loads(json.dumps(incoming))
        if attempt:
            hint = ("Start over. Say ONE complete sentence of no more than 24 words; "
                    "end it with a period or question mark. No lists, no subordinate "
                    "paragraphs or run-on clauses. Do not refer to yourself in the "
                    "third person. Make one concrete response to what was actually said. "
                    "Do not make up past events. Never write a line for Allen "
                    "or another participant; speak only as yourself.")
            prompt[0]["content"] += (
                " The previous candidate did not pass public conversational integrity "
                "checks (" + last_failure[:48] + "). " + hint)
        model_id = os.environ.get("ROOM_CHAT_MODEL_ID") or "Llama-3.2-1B-Instruct"
        body={"model":model_id,"messages":prompt,
              "temperature":.78 if not attempt else .62,"top_p":.9,
              "max_tokens":120 if not attempt else 100,
              "seed":seed,"stream":False}
        req=urllib.request.Request(
            url, data=json.dumps(body,ensure_ascii=False).encode(),
            headers={"Content-Type":"application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req,timeout=max(1,int(timeout))) as response:
                raw=json.loads(response.read().decode("utf-8","replace"))
            choices=raw.get("choices") or []
            data=choices[0].get("message") or {} if choices else {}
            spoken=str(data.get("content") or "").strip()
            labelled=SPEAKER_PREFIX.match(spoken)
            if labelled:
                if labelled.group(1).lower() != entity:
                    # Do not publish one agent's fabricated lines as Allen or
                    # another character. A real Allen turn is user-authored.
                    last_failure="wrong_speaker_label"
                    continue
                spoken=spoken[labelled.end():].strip()
            if not spoken or len(spoken)>700:
                last_failure="empty_or_overlong_candidate"
                continue
            if unfinished_model_quotation(spoken):
                last_failure="unclosed_model_quotation"
                continue
            if (issue:=autonomous_text_issue({"speaker":entity,"text":spoken})):
                last_failure=issue
                continue
            from room_private_model import _contains_explicit_leak_marker, _contains_meta_language
            if _contains_explicit_leak_marker(spoken) or _contains_meta_language(spoken):
                last_failure="model_process_or_privacy_marker"
                continue
            result=speech_metadata(spoken,payload,entity)
            # These are the SAME source-linked, speaker-bound publication
            # validators that run at preflight and final commit. Apply them
            # early so the local model can repair a candidate rather than
            # consuming a Room beat or manufacturing fallback speech.
            from room_private_commit import validate_public_expression, clean_terms
            from room_sequence_uptake import validate_uptake
            observed=witnessed_context(payload,entity)
            try:
                terms=clean_terms(result,payload.get("topic") or {},spoken)
                validate_public_expression(entity,spoken,terms,observed)
                validate_uptake(history=observed,speaker=entity,
                                utterance=spoken,move=result["move"])
                # A longer chat-model turn ending abruptly mid-sentence is
                # not a finished public action, even if older validators
                # tolerated the missing final punctuation. Short authentic
                # replies such as "No" remain valid.
                if (len(re.findall(r"[a-z0-9']+", spoken.casefold())) >= 10
                        and not spoken.rstrip().rstrip('"”’').endswith((".", "!", "?"))):
                    raise ValueError("unfinished_model_sentence")
            except (RuntimeError,ValueError) as exc:
                last_failure=str(exc)[:96]
                # Shadow-only diagnosis. Never print real Allen speech or
                # unseen private memories to an Actions log.
                if (os.environ.get("ROOM_CHAT_PUBLIC_SHADOW_DIAGNOSTIC") == "1"
                        and not any(h["speaker"]=="allen" for h in observed)):
                    print(f"SHADOW REJECTED {entity} attempt {attempt+1}: "
                          f"{last_failure}: {spoken[:460]!r}",flush=True)
                # The model sometimes continues after an already complete
                # sentence and ends mid-thought. Retain at most its own
                # complete, coherent spoken prefix. Do not synthesize text,
                # suppress a contrary clause, or bypass the hard validators.
                if any(key in last_failure for key in (
                        "wordy_expression", "run_on_expression", "trailing_fragment",
                        "unfinished_model_sentence")):
                    prefix=complete_model_prefix(spoken)
                    if prefix and prefix != spoken:
                        shortened=speech_metadata(prefix,payload,entity)
                        try:
                            prefix_terms=clean_terms(
                                shortened,payload.get("topic") or {},prefix)
                            validate_public_expression(
                                entity,prefix,prefix_terms,observed)
                            validate_uptake(
                                history=observed,speaker=entity,
                                utterance=prefix,move=shortened["move"])
                        except (RuntimeError,ValueError):
                            pass
                        else:
                            return shortened
                continue
            return result
        except (TimeoutError,urllib.error.URLError,ValueError,KeyError,TypeError,IndexError) as exc:
            last_failure=type(exc).__name__
            print(f"Room chat speech local generation attempt {attempt+1} failed for {entity}: {type(exc).__name__}")
            continue
    # Safe allowlisted-style failure category, never user text or the prompt.
    print(f"Room chat speech quarantined {entity}: {last_failure or 'unknown_invalid_response'}")
    return None
