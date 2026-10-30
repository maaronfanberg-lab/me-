#!/usr/bin/env python3
"""Source-grounded causal environment for a bounded Room conversation experiment.

No synthetic character speech or fabricated shared memories. An observation
becomes public only after its owner actually says it; a world action has an
effect only after an affirmative, attributed public utterance.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
import re

TRIAL_START = 36480
TRIAL_END = TRIAL_START + 240
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
    ('inspect_vent', r'inspect|inspected|check|checked|examine|examined|look at|looked at|take a closer look at|took a closer look at', r'air vent|rear vent|rear ventilation grille|rear grille|ventilation grille|projector vent|vent'),
    ('check_voltage', r'check|checked|inspect|inspected|measure|measured|test|tested', r'supply voltage|wall(?: socket)? voltage|socket voltage'),
    ('inspect_lamp', r'inspect|inspected|check|checked|examine|examined', r'lamp housing|projector lamp'),
    ('clear_vent', r'clear|cleared|unblock|unblocked|uncover|uncovered|clean|cleaned', r'air vent|rear vent|rear ventilation grille|rear grille|ventilation grille|projector vent|vent|folded cardboard|cardboard'),
    # Removing a grille is not equivalent to removing the obstructing cardboard.
    ('clear_vent', r'remove|removed|pull|pulled', r'folded cardboard|cardboard'),
    ('restart_projector', r'restart|restarted|switch on|switched on|turn on|turned on|power on|powered on', r'projector'),
)

def active(cycle: int) -> bool:
    return type(cycle) is int and TRIAL_START <= cycle < TRIAL_END

def production_cue(entity: str, *, root: Path | None = None,
                   next_cycle: int | None = None) -> str:
    """Read the *next* unpublished beat's scene from witnessed public history.

    Both the selected native-chat and legacy failback generators must see the
    same source-bound consequences. Persisted state.cycle names the LAST
    published beat, not the beat currently being generated.
    """
    if entity not in PEOPLE:
        return ''
    base = Path(root) if root is not None else Path(__file__).resolve().parents[1]
    try:
        if next_cycle is None:
            state = json.loads((base / 'room' / 'state.json').read_text())
            next_cycle = int(state.get('cycle', 0)) + 1
        if not active(next_cycle):
            return ''
        feed = json.loads((base / 'room' / 'feed.json').read_text())
        public = feed.get('conversation') or []
        if not isinstance(public, list):
            return ''
        return cue_for(entity, next_cycle, public)
    except (OSError, ValueError, TypeError, KeyError):
        # A missing or malformed feed never becomes fabricated scene evidence.
        return ''


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
    first = re.match(r'^\s*(?:I|we)\s+(?:just\s+|now\s+)?', phrase, re.I)
    if first is None:
        return None
    phrase = phrase[first.end():]
    if re.match(r"^(?:didn't|did not|never|can't|cannot|won't|will|want to|plan to|hope to)\b", phrase, re.I):
        return None
    for action, verbs, objects in _ACTIONS:
        pattern = rf'^(?:{verbs})\s+(?:the\s+|a\s+|my\s+)?(?:{objects})\b'
        match = re.match(pattern, phrase, re.I)
        if match:
            # A direct action can be followed by uncertainty about its cause:
            # "I cleared the rear grille, but it might still overheat."
            # Do not let that uncertainty erase the witnessed physical act.
            # A conditional action ("I clear the vent if...") is not witnessed.
            if re.match(r'\s+(?:only\s+)?if\b', phrase[match.end():], re.I):
                return None
            return action
    return None

def premature_action_result(speaker: str, text: str) -> bool:
    """An action may be witnessed now; its simulated outcome is not known yet.

    The world returns the result on the following beat. A model-generated
    inspection cannot author an additional circuit board, voltage reading or
    other consequence in the same breath. A standalone firsthand report with
    no action is not subject to this particular check.
    """
    if not witnessed_action(speaker, text):
        return False
    return re.search(
        r"\\b(?:reveal(?:s|ed|ing)?|discover(?:s|ed|ing)?|"
        r"find(?:s|ing)?|found|show(?:s|ed|ing)?|"
        r"expos(?:es|ed|ing)|turns out|"
        r"I (?:see|saw|notice|noticed)|there (?:is|are|was|were))\\b",
        text, re.I) is not None


def evidence_terms(text: str) -> set[str]:
    return set(re.findall(r'[a-z]{5,}', text.lower())) - {
        'there', 'their', 'which', 'about', 'noticed', 'before',
        'after', 'during', 'showed', 'report', 'reported', 'starts',
        'machine', 'projector', 'several', 'running', 'image',
    }

def stalled_scene(cycle: int, public_turns: list[dict]) -> bool:
    """Eight witnessed turns remain on one practical problem without progress.

    A physical act, a firsthand finding, or an actual subject transition resets
    the condition. This is evidence from public turns, not a topic-label guess.
    """
    if not active(cycle) or not isinstance(public_turns, list):
        return False
    recent = [turn for turn in public_turns
              if isinstance(turn, dict)
              and turn.get('speaker') in PEOPLE
              and (when := cycle_of(turn)) is not None
              and TRIAL_START <= when < cycle][-8:]
    if len(recent) < 8:
        return False
    scene = {'projector', 'dimming', 'grille', 'voltage', 'ventilation',
             'lamp', 'cardboard', 'thermal', 'dust', 'socket', 'agent'}
    on_topic = 0
    for turn in recent:
        spoken = str(turn.get('text') or '').strip()
        if witnessed_action(str(turn.get('speaker')), spoken):
            return False
        if re.match(r"^(?:I|we)\s+(?:saw|found|noticed|observed|measured|"
                    r"checked|decided|fixed|repaired|resolved)\b", spoken, re.I):
            return False
        terms = set(re.findall(r'[a-z]{4,}', spoken.lower()))
        if terms & scene:
            on_topic += 1
        elif re.search(r"\b(?:talk about|rather discuss|switch to|move on to)\b",
                       spoken, re.I):
            # An actual choice to change subjects ends the stuck-scene streak.
            return False
    # A brief anaphoric reply need not repeat the projector's name.
    return on_topic >= 6


def circular_deferral(speaker: str, candidate: str, cycle: int,
                      public_turns: list[dict]) -> bool:
    """Reject another speculative same-scene loop, not ordinary disagreement.

    The stalled condition is derived from actual consecutive public turns.
    Grounded findings, direct practical requests, actions, and topic transitions
    remain admissible. Rejected words are never replaced with synthetic speech.
    """
    if speaker not in PEOPLE or not isinstance(candidate, str):
        return False
    if not stalled_scene(cycle, public_turns):
        return False
    spoken = candidate.strip()
    if witnessed_action(speaker, spoken):
        return False
    if re.match(r"^(?:I|we)\s+(?:saw|found|noticed|observed|measured|"
                r"checked|decided|disagree|don't agree|cannot|can't|"
                r"refuse|decline)\b|^(?:no|yes)\b", spoken, re.I):
        return False
    # Requests for an observable finding or help with a concrete task advance
    # a joint activity; do not penalize them for being phrased as questions.
    if re.search(r"\b(?:did you (?:see|notice|measure|check|find)|"
                 r"what did you (?:see|find|measure|check)|"
                 r"what (?:does|did) the (?:monitor|meter|reading) (?:show|say)|"
                 r"could you (?:show|measure|inspect|check|remove|restart|hold|pass))\b",
                 spoken, re.I):
        return False
    scene = {'projector', 'dimming', 'grille', 'voltage', 'ventilation',
             'lamp', 'cardboard', 'thermal', 'dust', 'socket', 'agent'}
    if not (set(re.findall(r'[a-z]{4,}', spoken.lower())) & scene):
        return False
    # Earlier gate recognized only a few sentence openings. The live model
    # evaded it with "I think...", "it seems...", and question variants.
    # Classify the conversational act, not a prohibited list of subject words.
    return bool(
        spoken.endswith('?')
        or re.search(r"\b(?:what if|before we|can we|should we|we need to|"
                     r"we should|we could|let's|i think|i wonder|"
                     r"i'd like to|i would like to|it seems|"
                     r"perhaps|maybe|might|could be|possible|possibility|"
                     r"consider|revisit|focus on)\b", spoken, re.I)
    )


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
        action = witnessed_action(speaker, spoken)
        overlap = evidence_terms(spoken) & evidence_terms(PRIVATE[speaker])
        # Shared nouns are not a disclosure: "I measure the voltage" says
        # nothing about the monitor reading, and a question is not evidence.
        unasserted = (
            spoken.endswith('?')
            or re.match(r"^\s*(?:I\s+(?:think|wonder|suspect|guess|might|could|would|will|want)|"
                        r"we\s+(?:might|could|would|will|should)|maybe|perhaps|what if|let's)\b",
                        spoken, re.I) is not None
            or (action is not None and re.search(
                r"\b(?:found|noticed|observed|saw|showed|shows|stayed|steady|"
                r"reading|revealed|confirmed)\b", spoken, re.I) is None)
        )
        if len(overlap) >= 2 and speaker not in disclosures and not unasserted:
            disclosures[speaker] = {
                'speaker': speaker, 'text': spoken[:200], 'source_id': source_id,
            }
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
            'solved': solved, 'vent_cleared': cleared,
            'completed_actions': sorted(seen_actions)}

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
        # Give the small model executable, public-world affordances, not another
        # abstract question. These are possibilities, never invented actions.
        # The next turn remains entirely authored by the selected character.
        completed = set(state['completed_actions'])
        options = []
        if 'inspect_vent' not in completed:
            options.append('inspect the rear ventilation grille')
        if 'check_voltage' not in completed:
            options.append('measure the wall socket voltage')
        if 'inspect_lamp' not in completed:
            options.append('inspect the lamp housing')
        if not state['vent_cleared']:
            options.append('remove a visible obstruction from the grille, if one is found')
        elif 'restart_after_clear' not in completed:
            options.append('restart the projector and observe whether it stays bright')
        notice += (' The projector still dims; the practical cause has not been '
                   'established by a completed test. '
                   'Do not propose repeating a check already recorded as completed. '
                   'Available physical choices not yet completed: '
                   + '; '.join(options) + '. '
                   'If you choose to do one, describe the action as something you '
                   'actually do now (for example, "I inspect the rear grille"), '
                   'not a promise to do it later. Only witnessed actions change '
                   'the simulated environment. You may also decline or pursue '
                   "another person's important question.")
        recent = [turn for turn in public_turns
                  if isinstance(turn, dict)
                  and turn.get('speaker') in PEOPLE
                  and (when := cycle_of(turn)) is not None
                  and TRIAL_START <= when < cycle][-8:]
        if len(recent) >= 8 and not any(
                witnessed_action(str(turn.get('speaker')),
                                 str(turn.get('text') or ''))
                for turn in recent):
            notice += (' The last eight public turns contained no recognized '
                       'completed physical action; more causal guesses alone '
                       'will not test the projector.')
    return notice
