#!/usr/bin/env python3
"""Source-grounded causal environment for a bounded Room conversation experiment.

No synthetic character speech or fabricated shared memories. An observation
becomes public only after its owner actually says it; a world action has an
effect only after an affirmative, attributed public utterance.
"""
from __future__ import annotations
from dataclasses import dataclass
import re

TRIAL_START = 36320
TRIAL_END = TRIAL_START + 120
PEOPLE = ('sarah', 'mara', 'owen', 'jules')
COMMON = ('At the neighborhood planetarium, the projector repeatedly dims ten '
          'minutes into the astronomy show, although it starts normally.')
PRIVATE = {
    'sarah': 'You noticed that dimming starts only after the projector has run for several minutes.',
    'mara': 'A visitor near the projector reported a smell of hot dust just before the image faded.',
    'owen': 'The wall socket voltage monitor showed a steady reading during the dimming.',
    'jules': 'You noticed folded cardboard partly covering the projector rear ventilation grille.',
}

@dataclass(frozen=True)
class Consequence:
    source_id: str
    actor: str
    action: str
    observation: str

_ACTIONS = (
    ('inspect_vent', r'inspect|inspected|check|checked|examine|examined|look at|looked at', r'air vent|rear vent|ventilation grille|projector vent'),
    ('check_voltage', r'check|checked|inspect|inspected|measure|measured|test|tested', r'supply voltage|wall voltage|socket voltage'),
    ('inspect_lamp', r'inspect|inspected|check|checked|examine|examined', r'lamp housing|projector lamp'),
    ('clear_vent', r'clear|cleared|unblock|unblocked|uncover|uncovered|clean|cleaned', r'air vent|rear vent|ventilation grille|projector vent'),
    ('restart_projector', r'restart|restarted|switch on|switched on|turn on|turned on|power on|powered on', r'projector'),
)

def active(cycle: int) -> bool:
    return type(cycle) is int and TRIAL_START <= cycle < TRIAL_END

def cycle_of(turn: dict) -> int | None:
    try:
        return int(str(turn.get('beat_id') or '').rsplit('-', 1)[-1])
    except (ValueError, TypeError):
        return None

def witnessed_action(speaker: str, text: str) -> str | None:
    """Only affirmative first-person physical actions, not proposals or questions."""
    if speaker not in PEOPLE or not isinstance(text, str):
        return None
    phrase = text.strip()
    if not phrase or len(phrase) > 500 or phrase.endswith('?'):
        return None
    if re.search(r'\b(?:could|would|should|might|maybe|if|suppose|hypothetically|imagine)\b', phrase, re.I):
        return None
    first = re.match(r'^\s*(?:I|we)\s+(?:just\s+|now\s+)?', phrase, re.I)
    if first is None:
        return None
    phrase = phrase[first.end():]
    if re.match(r"^(?:didn't|did not|never|can't|cannot|won't|will|want to|plan to|hope to)\b", phrase, re.I):
        return None
    for action, verbs, objects in _ACTIONS:
        pattern = rf'^(?:{verbs})\s+(?:the\s+|a\s+|my\s+)?(?:{objects})\b'
        if re.match(pattern, phrase, re.I):
            return action
    return None

def evidence_terms(text: str) -> set[str]:
    return set(re.findall(r'[a-z]{5,}', text.lower())) - {
        'there', 'their', 'which', 'about', 'noticed', 'before',
        'after', 'during', 'showed', 'report', 'reported', 'starts',
        'machine', 'projector', 'several', 'running', 'image',
    }

def replay(cycle: int, turns: list[dict]) -> dict:
    """Reconstruct the world solely from past, identified public speech."""
    if not active(cycle):
        return {'active': False, 'effects': [], 'disclosures': [], 'solved': False}
    cleared, solved = False, False
    seen_actions: set[str] = set()
    seen_ids: set[str] = set()
    effects: list[Consequence] = []
    disclosures: dict[str, dict] = {}
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        speaker = str(turn.get('speaker') or '').lower()
        when = cycle_of(turn)
        source_id = str(turn.get('id') or '')
        if (when is None or not (TRIAL_START <= when < cycle) or not source_id
                or source_id in seen_ids):
            continue
        seen_ids.add(source_id)
        if speaker not in PEOPLE:
            continue
        spoken = str(turn.get('text') or '').strip()
        overlap = evidence_terms(spoken) & evidence_terms(PRIVATE[speaker])
        if len(overlap) >= 2 and speaker not in disclosures:
            disclosures[speaker] = {
                'speaker': speaker, 'text': spoken[:200], 'source_id': source_id,
            }
        action = witnessed_action(speaker, spoken)
        if not action:
            continue
        key = ('restart_after_clear' if cleared else 'restart_before_clear') if action == 'restart_projector' else action
        if key in seen_actions:
            continue
        seen_actions.add(key)
        observation = {
            'inspect_vent': 'The rear grille is packed with dust and blocked by folded cardboard.',
            'check_voltage': 'The socket voltage stays steady while the projector dims.',
            'inspect_lamp': 'The lamp housing is unusually hot; there is no visible broken bulb.',
            'clear_vent': 'The obstruction is removed and cool air flows through the grille.',
            'restart_before_clear': 'The projector starts but dims again after warming up.',
            'restart_after_clear': 'After the restart, the projector stays bright through the next ten minutes.',
        }[key]
        effects.append(Consequence(source_id, speaker, key, observation))
        if action == 'clear_vent':
            cleared = True
        if key == 'restart_after_clear':
            solved = True
    return {'active': True, 'effects': effects, 'disclosures': list(disclosures.values()),
            'solved': solved, 'vent_cleared': cleared}

def cue_for(entity: str, cycle: int, public_turns: list[dict]) -> str:
    """A situational cue for a real model, not a command to speak about the scene."""
    if entity not in PEOPLE or not active(cycle):
        return ''
    state = replay(cycle, public_turns)
    disclosed = {d['speaker'] for d in state['disclosures']}
    notice = (
        'BOUNDED FICTIONAL SHARED ENVIRONMENT (not a participant speaking): '
        + COMMON + ' This situation changes only when an agent actually performs '
        'an action in public speech. Do not claim an inspection was performed '
        'or an observation was shared unless public evidence supports it.'
    )
    if cycle == TRIAL_START:
        notice += ' This event is newly occurring AFTER the latest public turn.'
    if entity not in disclosed:
        notice += ' PRIVATE OBSERVATION KNOWN TO YOU ALONE: ' + PRIVATE[entity]
    else:
        notice += ' Your relevant private observation has already been shared publicly.'
    if state['disclosures']:
        notice += ' PUBLICLY WITNESSED EVIDENCE: ' + ' '.join(
            d['speaker'].capitalize() + ' said [' + d['source_id'] + ']: ' + d['text']
            for d in state['disclosures'][:4]
        )
    if state['effects']:
        notice += ' CHANGES OBSERVED AFTER PUBLIC ACTIONS: ' + ' '.join(
            e.actor.capitalize() + ' [' + e.source_id + ']: ' + e.observation
            for e in state['effects'][-4:]
        )
    if state['solved']:
        notice += (' The projector stayed bright after a witnessed restart. '
                   'The practical problem appears resolved, and other subjects are welcome.')
    else:
        notice += (' The cause is not yet established by public evidence. You may '
                   'investigate, ask, challenge, take a direct action or continue '
                   'a more interesting existing exchange. Nothing is mandatory.')
    return notice
