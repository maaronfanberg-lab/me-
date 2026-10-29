#!/usr/bin/env python3
"""Finite, source-linked Room follow-through memory.

A promise is not a completed act. This module neither scripts speech nor
changes the environment: it merely keeps published intentions available
until that same public speaker explicitly reports doing the relevant act.
"""
from __future__ import annotations
import re
from room_world_actions import _EFFECTS, _VERBS, _OBJECTS, action_consequence
from room_hidden_world import followup_active, active_scene_window, scene_for_cycle, scene_phase

PARTICIPANTS = ("sarah", "mara", "owen", "jules")
# Stage on the *second* followup scene only, not earlier choir baseline.
START = 36328
END = 36364

def active(cycle: int) -> bool:
    return type(cycle) is int and START <= cycle < END and followup_active(cycle) and active_scene_window(cycle)

def announced_plan(scene: str, speaker: str, utterance: str):
    if speaker not in PARTICIPANTS or not isinstance(utterance, str):
        return None
    text=utterance.strip()
    if not text or len(text)>500 or text.endswith("?"):
        return None
    # Test the self-commitment clause, not a later explanation of what will be
    # inspected. "I'll inspect the filter, to see if it is clogged" is an
    # intention; "I'll inspect it if someone asks" is conditional.
    head=text.split(",",1)[0]
    if re.search(r"\b(?:could|would|should|might|maybe|what if|hypothetically|imagine)\b",head,re.I):
        return None
    if re.search(r"\bif\b",head,re.I) and not re.search(r"\b(?:see|check|find out|know|tell)\s+if\b",head,re.I):
        return None
    # First person, affirmative, self-committing future. Not an imperative to somebody else.
    match=re.match(
        r"^\s*(?:I\s+think\s+)?(?:I'll|I\s+will|I'm\s+(?:just\s+)?going\s+to|I\s+am\s+going\s+to|We\s+will|We're\s+going\s+to)\s+",
        text, re.I)
    if not match:
        return None
    remainder=text[match.end():]
    remainder=re.sub(r"^(?:(?:go\s+ahead\s+and|try\s+to|just|now|carefully)\s+)*","",remainder,flags=re.I)
    for effect in _EFFECTS:
        if effect.scene != scene:
            continue
        verbs=_VERBS[effect.action]
        objects=_OBJECTS[effect.object]
        pattern=(r"^(?:"+"|".join(re.escape(v) for v in verbs)
                 +r")\s+(?:the\s+|a\s+|my\s+)?(?:"
                 +"|".join(re.escape(v) for v in objects)+r")\b")
        if re.match(pattern,remainder,flags=re.I):
            return (effect.action,effect.object)
    return None

def pending(cycle: int, public_turns: list[dict], limit: int=3) -> list[dict]:
    """Unfulfilled *stated* intentions of the same identified public actor only."""
    if not active(cycle) or not isinstance(public_turns,list):
        return []
    scene=scene_for_cycle(cycle).identifier
    onset=scene_phase(cycle)[1]
    seen=set()
    obligations={}
    for t in public_turns:
        if not isinstance(t,dict):
            continue
        speaker=str(t.get("speaker") or "").lower()
        if speaker not in PARTICIPANTS:
            continue
        sid=str(t.get("id") or "").strip()
        if not sid or sid in seen:
            continue
        try:
            at=int(str(t.get("beat_id") or "").rsplit("-",1)[-1])
        except (ValueError,TypeError):
            continue
        if not onset <= at < cycle:
            continue
        seen.add(sid)
        spoken=str(t.get("text") or "").strip()
        observed=action_consequence(scene,speaker,spoken)
        if observed:
            obligations.pop((speaker,observed["action"],observed["object"]),None)
        plan=announced_plan(scene,speaker,spoken)
        if plan:
            key=(speaker,plan[0],plan[1])
            obligations.setdefault(key,{
                "speaker":speaker,"action":plan[0],"object":plan[1],
                "source_id":sid,"public_text":spoken[:180],
                "status":"intention_unconfirmed"
            })
    return list(obligations.values())[-max(0,min(limit,5)):]

def notice(cycle: int, public_turns: list[dict], entity: str | None = None) -> str:
    """Source-bound, person-relevant tasks, without copying stale plan dialogue.

    Own commitments remain available as an opportunity, not an obligation.
    Other people's commitments are labelled as unperformed; neither the
    system nor a bystander is permitted to claim they did the action.
    """
    items=pending(cycle,public_turns)
    if not items:
        return ""
    if entity not in PARTICIPANTS:
        lines=["UNRESOLVED SPOKEN INTENTIONS FROM ACTUAL PUBLIC MESSAGES "
               "(not proof that these actions occurred, not a command to perform them):"]
        lines.extend(x["speaker"].capitalize()+" previously said ["+x["source_id"]+"]: "+x["public_text"] for x in items)
        lines.append("Someone may follow through, change their mind, ask a new question, "
                     "or do something else. Do not describe a planned action as completed "
                     "without a public first-person action statement.")
        return "\n".join(lines)
    own=[item for item in items if item["speaker"]==entity]
    others=[item for item in items if item["speaker"]!=entity]
    lines=["PENDING PHYSICAL ACTIVITY (public intentions, NOT completed acts):"]
    if own:
        for item in own[-2:]:
            lines.append(
                "Your earlier stated plan ["+item["source_id"]+"] was to "
                +item["action"]+" the "+item["object"]+
                ". No completed inspection or outcome has been witnessed. "
                "You can act now, decline, or do something else."
            )
    if others:
        lines.append(
            "Other participants have announced but not yet completed: "
            +"; ".join(item["speaker"].capitalize()+" "+item["action"]+
                         " "+item["object"] for item in others[-2:])
            +". These are not observations of results."
        )
    return "\n".join(lines)
