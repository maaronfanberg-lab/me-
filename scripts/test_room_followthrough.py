#!/usr/bin/env python3
from room_followthrough import announced_plan, pending, notice, active, START, END
from room_hidden_world import FOLLOWUP_START, FOLLOWUP_END
from room_world_actions import action_consequence

def turn(cycle,speaker,text,ident=None):
    return {"id":ident or str(cycle),"speaker":speaker,"text":text,
            "beat_id":"beat-test-%06d"%cycle}

assert FOLLOWUP_START < START < END <= FOLLOWUP_END
assert not active(START-1) and active(START) and active(END-1) and not active(END)
scene="greenhouse-watering"
for phrasing in ("I'll open the supply valve.","I will open the supply valve.",
                 "I'm going to open the supply valve.","I'm just going to open the supply valve.",
                 "I'll just go ahead and open the supply valve."):
    assert announced_plan(scene,"jules",phrasing)==("open","supply valve"),phrasing
for phrasing in ("I might open the supply valve.","We should open the supply valve.",
                 "I could open the supply valve.","What if I open the supply valve?",
                 "I opened the supply valve.","I'll open the supply valve?",
                 "I will definitely open it if someone asks."):
    assert announced_plan(scene,"jules",phrasing) is None, phrasing
# Regression from the actual published cycle 36329 (natural future action).
assert announced_plan(scene,"jules",
    "I'm going to check the irrigation filter, since it's the first thing I noticed that might be causing the issue, and see if it's clogged or dirty, as a clogged filter could be preventing water from flowing properly.") == ("inspect","irrigation filter")
assert announced_plan(scene,"jules","I'll inspect the irrigation filter to see if it's clogged.") == ("inspect","irrigation filter")
assert announced_plan(scene,"jules","I'll inspect the irrigation filter if somebody asks.") is None
assert announced_plan(scene,"allen","I'll open the supply valve.") is None
assert announced_plan(scene,"jules","I'll move the microphone cable.") is None

source=[
    turn(START,"jules","I'll open the supply valve.","j0"),
    turn(START+1,"owen","I'm going to inspect the irrigation filter.","o1"),
    turn(START+2,"jules","I could open the supply valve.","j2"),
    turn(START+3,"mara","I heard Jules was going to open the valve.","m3"),
    turn(START+4,"allen","I'll open the supply valve.","a4"),
]
a=pending(START+5,source)
assert len(a)==2
assert {x["source_id"] for x in a}=={"j0","o1"}
assert "not proof" in notice(START+5,source)
own_notice=notice(START+5,source,entity="jules")
assert "Your earlier stated plan [j0]" in own_notice
assert "No completed inspection or outcome has been witnessed" in own_notice
assert "Other participants have announced but not yet completed: Owen inspect irrigation filter" in own_notice
assert "Jules previously said" not in own_notice
# Later plans by other people must not erase the speaker's own still-open plan.
crowded=source+[turn(START+5,"sarah","I'll inspect the irrigation filter.","s5"),
                turn(START+6,"mara","I'll open the supply valve.","m6"),
                turn(START+7,"owen","I'll open the supply valve.","o7")]
assert "Your earlier stated plan [j0]" in notice(START+8,crowded,entity="jules")
partner_notice=notice(START+5,source,entity="mara")
assert "Jules open supply valve" in partner_notice
assert "Your earlier stated plan" not in partner_notice
assert "j0" in notice(START+5,source)
assert {x["source_id"] for x in pending(START+2,source)} == {"j0","o1"}
assert {x["source_id"] for x in pending(START+1,source)} == {"j0"} # no future sources
# Owen's completed action resolves only Owen's plan, not Jules'.
after=source+[turn(START+5,"owen","I inspect the irrigation filter.","o5")]
assert len(pending(START+6,after))==1
assert pending(START+6,after)[0]["speaker"]=="jules"
done=after+[turn(START+6,"jules","I open the supply valve.","j6")]
assert not pending(START+7,done)
assert not pending(END,done)
assert action_consequence(scene,"jules","I'll open the supply valve.") is None
assert action_consequence(scene,"jules","I open the supply valve.") is not None
assert not pending(START+7,done+[turn(START+6,"jules","I open the supply valve.","j6")])
assert not pending(START+7,[turn(START-1,"jules","I'll open the supply valve.")])
# Test actual expression-context integration with a mocked public feed.
import json
import os
from unittest.mock import patch
from room_chat_speech import messages
payload={"entity":"mara","profile":{},"room_cycle":START+5,
         "context":[{"id":"o1","speaker":"owen","text":"I'm going to inspect the irrigation filter."}]}
flags={"ROOM_HIDDEN_WORLD_EXPERIMENT":"1","ROOM_SCENE_PUBLIC_LEDGER":"1",
       "ROOM_WORLD_ACTIONS":"1","ROOM_PLAN_FOLLOWTHROUGH":"1"}
with patch.dict(os.environ,flags):
    with patch("pathlib.Path.read_text",return_value=json.dumps({"conversation":source})):
        rendered=messages(payload,"mara")
assert "UNRESOLVED SPOKEN INTENTIONS" in rendered[1]["content"]
assert "j0" in rendered[1]["content"] and "o1" in rendered[1]["content"]
assert "not proof" in rendered[1]["content"]
visitor=dict(payload,context=[{"speaker":"allen","text":"Please answer my question.","id":"allen-turn"}])
with patch.dict(os.environ,flags):
    with patch("pathlib.Path.read_text",return_value=json.dumps({"conversation":source})):
        reply=messages(visitor,"mara")
assert "UNRESOLVED SPOKEN INTENTIONS" not in reply[1]["content"]
with patch.dict(os.environ,flags):
    later=messages(dict(payload,room_cycle=END),"mara")
assert "UNRESOLVED SPOKEN INTENTIONS" not in later[1]["content"]

print("PASS: source-bound plans, actor-specific completion, no false action, expiry, visitors, and time boundaries")

# Production regression: the speech adapter may receive only two upstream
# messages even though earlier completed actions are still in the public feed.
from room_chat_speech import witnessed_context
public_tail=[
    turn(START+i,["jules","owen","mara","sarah"][i%4],
         ("I checked the pressure gauge." if i==3 else
          "I tightened the hose connector." if i==5 else
          "The greenhouse beds are still drying."), "recent-%02d"%i)
    for i in range(10)
]
visitor={"id":"visitor-new","speaker":"allen",
         "text":"What actually changed after the repair?"}
short_context={"context":public_tail[-2:],"event":visitor}
with patch("pathlib.Path.read_text",
           return_value=json.dumps({"conversation":public_tail})):
    retained=witnessed_context(short_context,"mara")
assert len(retained)==8,retained
assert retained[0]["id"]=="recent-03"
assert retained[-1]["id"]=="visitor-new"
assert "I tightened the hose connector." in [t["text"] for t in retained]
assert len({t["id"] for t in retained})==8
with patch("pathlib.Path.read_text",side_effect=OSError("no public feed")):
    fallback=witnessed_context(short_context,"mara")
assert [t["id"] for t in fallback]==["recent-08","recent-09","visitor-new"]
print("PASS: production short-context speech retains public action evidence and Allen priority")
