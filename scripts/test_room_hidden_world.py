#!/usr/bin/env python3
from __future__ import annotations
import os
from unittest.mock import patch
import room_hidden_world as h
import room_chat_speech as chat

for scene_index, scene in enumerate(h.SCENES):
    cycle = scene_index * h.EPISODE_TURNS
    assert h.scene_for_cycle(cycle + 1) == scene
    assert len(set(scene.observations)) == 4
    for entity in h.PARTICIPANTS:
        note = h.context_for(entity, cycle)
        assert scene.common in note
        assert h.private_observation(entity, cycle) in note
        for other in h.PARTICIPANTS:
            if other != entity:
                assert h.private_observation(other, cycle) not in note

payload = {'entity':'sarah', 'room_cycle':h.TRIAL_START, 'profile':{}, 'context':[{'speaker':'mara','text':'I noticed something unusual.'}]}
with patch.dict(os.environ, {'ROOM_HIDDEN_WORLD_EXPERIMENT':'0'}):
    baseline = chat.messages(payload, 'sarah')
assert h.scene_for_cycle(h.TRIAL_START).common not in baseline[0]['content']
with patch.dict(os.environ, {'ROOM_HIDDEN_WORLD_EXPERIMENT':'1'}):
    experimental = chat.messages(payload, 'sarah')
assert h.scene_for_cycle(h.TRIAL_START).common in experimental[0]['content']
for other in ('mara','owen','jules'):
    assert h.private_observation(other, h.TRIAL_START) not in experimental[0]['content']
visitor = dict(payload, context=[{'speaker':'allen','text':'Please help me with an unrelated matter.'}])
with patch.dict(os.environ, {'ROOM_HIDDEN_WORLD_EXPERIMENT':'1'}):
    answer = chat.messages(visitor, 'sarah')
assert h.scene_for_cycle(h.TRIAL_START).common not in answer[0]['content']
print('PASS: optional scene information, isolated observations and visitor priority')

assert h.trial_active(h.TRIAL_START)
assert h.trial_active(h.TRIAL_END - 1)
assert not h.trial_active(h.TRIAL_START - 1)
assert not h.trial_active(h.TRIAL_END)
with patch.dict(os.environ, {'ROOM_HIDDEN_WORLD_EXPERIMENT':'1'}):
    after = chat.messages(dict(payload, room_cycle=h.TRIAL_END), 'sarah')
assert h.scene_for_cycle(h.TRIAL_END).common not in after[0]['content']

assert h.event_at(h.TRIAL_START + 15)
assert h.event_at((h.TRIAL_START // h.EPISODE_TURNS + 1) * h.EPISODE_TURNS)
assert not h.event_at(h.TRIAL_START + 14)
assert not h.event_at(h.TRIAL_END)
with patch.dict(os.environ, {'ROOM_HIDDEN_WORLD_EXPERIMENT':'1'}):
    cue = chat.messages(dict(payload, room_cycle=h.TRIAL_START + 15), 'sarah')
assert 'new environmental event' in cue[1]['content'].lower()
assert h.private_observation('sarah', h.TRIAL_START+15) in cue[1]['content']
for other in ('mara','owen','jules'):
    assert h.private_observation(other, h.TRIAL_START + 15) not in cue[1]['content']
with patch.dict(os.environ, {'ROOM_HIDDEN_WORLD_EXPERIMENT':'1'}):
    nonevent = chat.messages(dict(payload, room_cycle=h.TRIAL_START + 16), 'sarah')
assert 'new environmental event' not in nonevent[1]['content'].lower()
with patch.dict(os.environ, {'ROOM_HIDDEN_WORLD_EXPERIMENT':'1'}):
    realvisitor = chat.messages(dict(visitor, room_cycle=h.TRIAL_START + 15), 'sarah')
assert 'new environmental event' not in realvisitor[1]['content'].lower()

assert h.scene_for_cycle(h.GROUNDING_ONSET).identifier == "garden-irrigation"
assert h.scene_for_cycle(h.GROUNDING_SECOND_ONSET).identifier == "lantern-festival"
assert h.event_at(h.GROUNDING_ONSET)
assert h.event_at(h.GROUNDING_SECOND_ONSET)
assert not h.event_at(h.GROUNDING_ONSET + 1)
assert h.active_scene_window(h.GROUNDING_ONSET)
assert h.active_scene_window(h.GROUNDING_ONSET + h.GROUNDING_WINDOW - 1)
assert not h.active_scene_window(h.GROUNDING_ONSET + h.GROUNDING_WINDOW)
assert not h.situational_notice("sarah", h.TRIAL_END)
with patch.dict(os.environ, {"ROOM_HIDDEN_WORLD_EXPERIMENT": "1"}):
    grounded = chat.messages(dict(payload, room_cycle=h.GROUNDING_ONSET + 1), "sarah")
assert "ONGOING FICTIONAL SITUATION" in grounded[1]["content"]
assert h.private_observation("sarah", h.GROUNDING_ONSET + 1) in grounded[1]["content"]
assert h.private_observation("owen", h.GROUNDING_ONSET + 1) not in grounded[1]["content"]
assert "Sarah:" not in grounded[1]["content"].split("ONGOING FICTIONAL SITUATION")[-1]
with patch.dict(os.environ, {"ROOM_HIDDEN_WORLD_EXPERIMENT": "1"}):
    visitor_grounded = chat.messages(dict(visitor, room_cycle=h.GROUNDING_ONSET), "sarah")
assert "ONGOING FICTIONAL SITUATION" not in visitor_grounded[1]["content"]
with patch.dict(os.environ, {"ROOM_HIDDEN_WORLD_EXPERIMENT": "1"}):
    expired = chat.messages(dict(payload, room_cycle=h.GROUNDING_ONSET + h.GROUNDING_WINDOW), "sarah")
assert "ONGOING FICTIONAL SITUATION" not in expired[1]["content"]

assert h.active_scene_window(h.GROUNDING_SECOND_ONSET + 23)
assert not h.active_scene_window(h.GROUNDING_SECOND_ONSET + 36)
