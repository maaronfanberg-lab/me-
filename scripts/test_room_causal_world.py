#!/usr/bin/env python3
import room_causal_world as w
import room_hidden_world as earlier

def turn(n, who, text, uid=None):
    return {'id': uid or str(n), 'speaker':who, 'text':text,
            'beat_id':'beat-test-%06d' % n}

assert w.TRIAL_END - w.TRIAL_START == 240
assert w.TRIAL_START >= earlier.FOLLOWUP_END, 'independent trials must not run simultaneously'
for n in (w.TRIAL_START-1, w.TRIAL_END, True): assert not w.active(n)
assert w.active(w.TRIAL_START) and w.active(w.TRIAL_END-1)
for who in w.PEOPLE:
    cue = w.cue_for(who, w.TRIAL_START, [])
    assert w.PRIVATE[who] in cue
    for other in w.PEOPLE:
        if other != who: assert w.PRIVATE[other] not in cue
for text in ('I could check the air vent.', 'I will check the air vent.',
             'I did not check the air vent.', 'If I check the air vent, what then?',
             'Would you check the air vent?', 'I want to check the air vent.'):
    assert w.witnessed_action('sarah', text) is None, text
assert w.witnessed_action('sarah','I inspect the air vent.') == 'inspect_vent'
assert w.witnessed_action('mara','We clear the ventilation grille.') == 'clear_vent'
assert w.witnessed_action('allen','I clear the air vent.') is None
assert w.witnessed_action('owen','I checked the supply voltage.') == 'check_voltage'
assert w.witnessed_action('jules','I restarted the projector.') == 'restart_projector'
assert w.witnessed_action('mara','We cleared the ventilation grille.') == 'clear_vent'
# Verbatim live Room speech at cycle 36567 must produce a voltage result.
assert w.witnessed_action('owen',
    'I measure the wall socket voltage to see if it is a correlation with the dimming.') == 'check_voltage'
assert w.witnessed_action('owen',
    'I checked the wall socket voltage.') == 'check_voltage'
# Removing a protective grille does NOT establish that the blockage was cleared.
assert w.witnessed_action('owen',
    'I remove the rear ventilation grille.') is None
assert w.witnessed_action('jules',
    'I pull the cardboard out of the rear grille.') == 'clear_vent'
# Live-dialogue affordances: people refer to the rear grille and cardboard,
# not just the canonical "air vent" name in the action schema.
assert w.witnessed_action('sarah',
    'I take a closer look at the rear ventilation grille.') == 'inspect_vent'
assert w.witnessed_action('jules',
    'I remove the folded cardboard.') == 'clear_vent'
assert w.witnessed_action('mara',
    'I cleared the rear grille, but it might still overheat.') == 'clear_vent'
assert w.witnessed_action('owen',
    'I check the rear vent, but maybe the lamp is also faulty.') == 'inspect_vent'
for unperformed in (
    'I clear the vent if the light goes out.',
    'I check the rear grille only if the projector dims.',
    'I might remove the cardboard.',
    'I would pull the cardboard away.',
):
    assert w.witnessed_action('sarah', unperformed) is None, unperformed
for negative in ("I didn't clear the air vent.", "I should have checked the voltage.",
                 "I could have restarted the projector."):
    assert w.witnessed_action('mara',negative) is None

s = w.TRIAL_START
history = [
    turn(s,'sarah','I inspect the air vent.'),
    turn(s+1,'mara','I wonder whether we should clear the vent?'),
    turn(s+2,'owen','I check the supply voltage.'),
    turn(s+3,'jules','I restart the projector.'),
    turn(s+4,'mara','We clear the ventilation grille.'),
    turn(s+5,'jules','I restart the projector.'),
]
state=w.replay(s+6,history)
assert [e.action for e in state['effects']] == [
    'inspect_vent','check_voltage','restart_before_clear','clear_vent','restart_after_clear']
assert state['solved']
# The exact names the fictional world supplies must lead to consequences.
natural = [
    turn(s, 'sarah', 'I inspect the rear ventilation grille.'),
    turn(s+1, 'jules', 'I remove the folded cardboard.'),
    turn(s+2, 'owen', 'I restart the projector.'),
]
natural_state = w.replay(s+3, natural)
assert [e.action for e in natural_state['effects']] == [
    'inspect_vent', 'clear_vent', 'restart_after_clear'
]
assert natural_state['solved']
# The live scene should not keep suggesting an already witnessed voltage test.
measured = [turn(s, 'owen', 'I measure the wall socket voltage.')]
voltage_state = w.replay(s+1, measured)
assert voltage_state['completed_actions'] == ['check_voltage']
assert 'socket voltage stays steady' in voltage_state['effects'][0].observation
next_cue = w.cue_for('mara', s+1, measured)
assert 'measure the wall socket voltage' not in next_cue
assert 'inspect the rear ventilation grille' in next_cue
# An inspection is not removal; it must not make the projector stay bright.
only_grille_removed = [turn(s, 'owen', 'I remove the rear ventilation grille.'),
                       turn(s+1, 'jules', 'I restart the projector.')]
assert not w.replay(s+2, only_grille_removed)['solved']
assert 'stays bright' in w.cue_for('owen',s+6,history)
assert not w.replay(s+4,history)['solved']
assert len(w.replay(s+3,history)['effects']) == 2
assert len(w.replay(s+7,history+[turn(s+6,'sarah','I inspect the air vent.')])['effects']) == 5
fact=turn(s+1,'sarah','The dimming starts after the projector has run for several minutes.')
d=w.replay(s+2,[fact])['disclosures']
assert len(d)==1 and d[0]['source_id']==fact['id']
assert w.PRIVATE['mara'] not in w.cue_for('owen',s+2,[fact])
assert w.PRIVATE['sarah'] not in w.cue_for('sarah',s+2,[fact])
# Regression based on eight consecutive real public Room turns (36538-36545).
# Each advanced the projector theory without a witnessed physical action.
live_loop = [
    turn(36538, 'owen', "The smell of hot dust seems too specific to be just a coincidence - is it possible that the projector's thermal management system is producing an abnormal heat signature that's being detected by the visitor?"),
    turn(36539, 'mara', "The smell of hot dust seems like an obvious trigger, but have we considered that it might be a result of the projector's own malfunctioning thermal management system, rather than a environmental factor?"),
    turn(36540, 'owen', "Is the cardboard grille's potential makeshift air filter being driven by a specific temperature threshold that's being exceeded by the projector's thermal management system?"),
    turn(36541, 'mara', "I'd like to probe further into the visitor's claim of the smell of hot dust - what's the duration of the smell, does it persist throughout the dimming event, and has anyone noticed any other environmental factors, like unusual lighting or temperature fluctuations?"),
    turn(36542, 'owen', "The visitor's claim of the smell of hot dust seems like a crucial lead - can we confirm the duration of the smell and whether it persists throughout the entire dimming event?"),
    turn(36543, 'mara', "Let's consider the cardboard grille as a potential culprit, but also examine the environmental factors that might be influencing the projector's behavior – Jules, did you notice any unusual temperature fluctuations or air circulation patterns near the projector during the show?"),
    turn(36544, 'owen', "Before we dive deeper into the potential causes, I think it's essential to consider the projector's internal thermal management system – is it possible that the agent's speech triggers a specific sequence of events that compromises the system's performance, resulting in the dimming?"),
    turn(36545, 'mara', "That's a great point about the smell of hot dust – it's almost as if we're being primed to notice something unusual, rather than actually detecting a temperature fluctuation."),
]
assert w.replay(36546, live_loop)['effects'] == []
stalled_cue = w.cue_for('jules', 36546, live_loop)
assert 'last eight public turns contained no recognized completed physical action' in stalled_cue
assert 'inspect the rear ventilation grille' in stalled_cue
assert 'remove a visible obstruction' in stalled_cue
assert 'restart the projector and observe' not in stalled_cue
# Actual action consequences must replace speculation without pretending anyone acted.
resolved_loop = live_loop + [
    turn(36546, 'jules', 'I inspect the rear grille.'),
    turn(36547, 'mara', 'I remove the folded cardboard.'),
    turn(36548, 'owen', 'I restart the projector.'),
]
assert w.replay(36549, resolved_loop)['solved']
assert 'last eight public turns contained no recognized completed physical action' not in w.cue_for('sarah', 36549, resolved_loop)
assert 'practical problem appears resolved' in w.cue_for('sarah', 36549, resolved_loop)

assert w.cue_for('sarah',w.TRIAL_END,history)==''

# Production regression: the next unpublished beat must include the latest
# published witnessed action, even though state.cycle names that last beat.
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    (root / 'room').mkdir()
    latest = turn(s+2, 'jules', 'I remove the folded cardboard.')
    (root / 'room' / 'state.json').write_text(json.dumps({'cycle': s+2}))
    (root / 'room' / 'feed.json').write_text(json.dumps({'conversation': [latest]}))
    cue = w.production_cue('sarah', root=root)
    assert latest['id'] in cue
    assert 'obstruction is removed' in cue
    assert 'PRIVATE OBSERVATION KNOWN TO YOU ALONE' in cue
    assert w.PRIVATE['jules'] not in cue
    assert w.production_cue('allen', root=root) == ''
    (root / 'room' / 'feed.json').write_text('{malformed')
    assert w.production_cue('sarah', root=root) == ''

# Both real speech paths must receive the same grounded world cue. Legacy
# failback must not silently turn an active experiment into empty speculation.
import room_private_model_autonomy_legacy as legacy
import room_chat_speech as chat
scene = 'BOUNDED FICTIONAL SHARED ENVIRONMENT: source-linked action happened.'
with patch.dict(os.environ, {'ROOM_CAUSAL_WORLD_EXPERIMENT': '1',
                             'ROOM_CONVERSATIONAL_FLOOR': '0',
                             'ROOM_HIDDEN_WORLD_EXPERIMENT': '0'}):
    with patch('room_causal_world.production_cue', return_value=scene) as cue_reader:
        compact = legacy._autonomy_compact(
            {'entity':'sarah', 'profile':{}, 'context':[], 'event':None,
             'topic':{}, 'partner':'mara'}, 'expression', 'sarah')
        assert compact['situated_environment'] == scene
        cue_reader.assert_called_once_with('sarah')
        visitor = legacy._autonomy_compact(
            {'entity':'sarah', 'profile':{}, 'context':[],
             'event':{'id':'allen-1', 'speaker':'allen',
                      'text':'I need help with something else.'},
             'topic':{}, 'partner':'allen'}, 'expression', 'sarah')
        assert 'situated_environment' not in visitor
        cue_reader.assert_called_once_with('sarah')
with patch.dict(os.environ, {'ROOM_CAUSAL_WORLD_EXPERIMENT': '1',
                             'ROOM_HIDDEN_WORLD_EXPERIMENT': '0'}):
    with patch('room_causal_world.production_cue', return_value=scene):
        recent = [{'id':str(n), 'speaker':'mara', 'text':'The lamp dims.'}
                  for n in range(8)]
        prompt = chat.messages({'context':recent, 'room_presence':{
            'present':list(w.PEOPLE)}}, 'sarah')
        assert scene in prompt[-1]['content']

print('PASS: finite test, provenance, private facts, source time ordering, actions, outcome and expiration')
