#!/usr/bin/env python3
import room_causal_world as w
import room_hidden_world as earlier

def turn(n, who, text, uid=None):
    return {'id': uid or str(n), 'speaker':who, 'text':text,
            'beat_id':'beat-test-%06d' % n}

assert w.TRIAL_END - w.TRIAL_START == 120
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
assert 'stays bright' in w.cue_for('owen',s+6,history)
assert not w.replay(s+4,history)['solved']
assert len(w.replay(s+3,history)['effects']) == 2
assert len(w.replay(s+7,history+[turn(s+6,'sarah','I inspect the air vent.')])['effects']) == 5
fact=turn(s+1,'sarah','The dimming starts after the projector has run for several minutes.')
d=w.replay(s+2,[fact])['disclosures']
assert len(d)==1 and d[0]['source_id']==fact['id']
assert w.PRIVATE['mara'] not in w.cue_for('owen',s+2,[fact])
assert w.PRIVATE['sarah'] not in w.cue_for('sarah',s+2,[fact])
assert w.cue_for('sarah',w.TRIAL_END,history)==''
print('PASS: finite test, provenance, private facts, source time ordering, actions, outcome and expiration')
