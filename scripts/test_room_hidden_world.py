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
