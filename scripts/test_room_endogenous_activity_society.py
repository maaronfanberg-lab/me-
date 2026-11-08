#!/usr/bin/env python3
"""Model-choice contracts, provenance, social consequences and quiet-world tests."""
from __future__ import annotations

import copy
import json
import unittest
from room_endogenous_activity_society import (
    initial_society, activity_beat, speech_messages, parse_voluntary_speech,
    SILENCE,
)
from room_endogenous_activity_world import AGENTS, activity_messages, agent_view

PROFILES = {a: {'core_identity': f'{a} is an independent observer with different interests.'}
            for a in AGENTS}


def encoded(kind='wait', **kwargs):
    payload = {'kind': kind, 'channel':'', 'device':'', 'setting':0.0,
               'horizon':1, 'control':'current', 'window':2, 'source_id':''}
    payload.update(kwargs)
    return json.dumps(payload)


def run(society, selector, speaker=None, *, beat=None, awake=AGENTS, budget=2):
    return activity_beat(society=society,
         expected_revision=society['revision'],
         cycle_id=beat or f'society-{society["revision"]+1}',
         profiles=PROFILES, choose_activity=selector, choose_speech=speaker,
         awake=awake, speech_budget=budget)


class SocietyTests(unittest.TestCase):
    def test_no_model_discoveries_needed_to_keep_world_alive(self):
        s=initial_society()
        untouched=copy.deepcopy(s)
        for k in range(45):
            s, report = run(s, lambda m,o: encoded('wait'))
            self.assertEqual(report['publications'],0)
            self.assertEqual(report['new_receipts'],0)
            self.assertEqual(report['model_calls'],4)
        self.assertEqual(s['world']['tick'],45)
        self.assertNotEqual(s['world']['environment'],untouched['world']['environment'])
        self.assertEqual(s['conversation'],[])

    def test_four_agent_choices_execute_distinct_verifiable_work(self):
        s=initial_society()
        choices={
            'sarah':encoded('calibrate',channel='temperature'),
            'mara':encoded('observe',channel='oxygen'),
            'owen':encoded('forecast',channel='algae',horizon=8,control='shade'),
            'jules':encoded('intervene',device='shade',setting=.7),
        }
        s, info=run(s,lambda messages, owner:choices[owner])
        self.assertEqual(info['model_calls'],4)
        self.assertEqual(info['new_receipts'],4)
        self.assertEqual(info['control_changes'],1)
        self.assertEqual(info['publications'],0)
        self.assertEqual(s['world']['controls']['shade'],.7)
        self.assertEqual(set(info['agent_choices'].values()),
                         {'observe','calibrate','forecast','intervene'})
        for owner in AGENTS:
            self.assertEqual(len(s['world']['private_notebooks'][owner]),1)
            ids={r['id'] for r in agent_view(s['world'],owner)['own_witnessed_records']}
            for peer in AGENTS:
                if peer!=owner:
                    self.assertNotIn(s['world']['private_notebooks'][peer][0]['id'],ids)

    def test_character_can_speak_only_from_own_tool_receipt(self):
        s=initial_society()
        def independent(messages,owner):
            return encoded('observe',channel='algae' if owner=='jules' else 'temperature')
        def maybe_speak(messages,owner):
            data=json.loads(messages[1]['content'])
            own=data['my_experiences']['own_witnessed_records'][-1]
            words=f"I ran a simulated {own['kind']} probe and it reported {own['result']['reported']} units."
            return json.dumps({'utterance':words,'source_id':own['id']})
        s, r=run(s,independent,maybe_speak,awake=('sarah',),budget=1)
        self.assertEqual(r['publications'],1)
        self.assertEqual(r['model_calls'],2)
        self.assertEqual(len(s['conversation']),1)
        line=s['conversation'][0]
        self.assertEqual(line['speaker'],'sarah')
        self.assertEqual(line['source_id'],s['world']['private_notebooks']['sarah'][-1]['id'])
        self.assertIn('simulated',line['text'])

    def test_peer_private_receipt_id_cannot_authorize_speech(self):
        s=initial_society()
        s, _=run(s,lambda m,o:encoded('observe',channel='oxygen'))
        seen=s['world']['private_notebooks']['mara'][0]['id']
        reported=json.dumps({'utterance':'I checked this numerical oxygen reading.',
                             'source_id':seen})
        self.assertIsNone(parse_voluntary_speech(reported,owner='sarah',world=s['world'],previous=[]))

    def test_fabricated_numeric_claim_cannot_be_published(self):
        s=initial_society()
        s, _=run(s,lambda m,o:encoded('observe',channel='oxygen'))
        source=s['world']['private_notebooks']['sarah'][0]['id']
        claim=json.dumps({'utterance':'I measured 99999 oxygen units, so everything is solved.',
                          'source_id':source})
        self.assertIsNone(parse_voluntary_speech(claim,owner='sarah',world=s['world'],previous=[]))

    def test_speaker_can_decline_despite_having_a_verified_discovery(self):
        s=initial_society()
        s, report=run(s,lambda m,o:encoded('observe',channel='oxygen'),
                      lambda m,o:SILENCE)
        self.assertEqual(report['new_receipts'],4)
        self.assertEqual(report['publications'],0)
        self.assertEqual(report['model_calls'],6)
        self.assertEqual(s['conversation'],[])

    def test_unavailable_model_is_not_replaced_by_scripted_experiment(self):
        s=initial_society()
        def offline(*_): raise TimeoutError('local 3B offline')
        s,report=run(s,offline,offline)
        self.assertEqual(report['new_receipts'],0)
        self.assertEqual(report['publications'],0)
        self.assertEqual(s['world']['tick'],1)
        self.assertEqual(report['model_calls'],4)
        self.assertEqual(len(report['model_failures']),4)

    def test_duplicate_beat_does_not_requery_llm(self):
        s=initial_society()
        first, r=run(s,lambda m,o:encoded('observe',channel='oxygen'),beat='first')
        def no_request(*_): raise AssertionError('repeated model inference')
        same, replay=run(first,no_request,beat='first')
        self.assertTrue(replay['replayed'])
        self.assertEqual(replay['model_calls'],0)
        self.assertEqual(first,same)

    def test_speech_uses_public_shared_evidence_not_private_forged_omniscience(self):
        s=initial_society()
        s,_=run(s,lambda m,o:encoded('observe',channel='oxygen') if o=='jules' else encoded('wait'))
        source=s['world']['private_notebooks']['jules'][0]['id']
        s,r=run(s,lambda m,o:encoded('share',source_id=source) if o=='jules' else encoded('wait'))
        self.assertEqual(r['new_shared_evidence'],1)
        msgs=speech_messages(owner='owen',profile=PROFILES['owen'],world=s['world'],public_history=[])
        parsed=json.loads(msgs[1]['content'])
        self.assertEqual(parsed['my_experiences']['own_witnessed_records'],[])
        self.assertEqual(parsed['my_experiences']['shared_computed_evidence'][0]['source_id'],source)
        self.assertIn(source,parsed['verified_sources_i_can_cite'])
        report=s['world']['public_evidence'][0]
        out=json.dumps({'utterance':'I noticed Jules shared a simulated sensor result.',
                        'source_id':source})
        self.assertIsNotNone(parse_voluntary_speech(out,owner='owen',world=s['world'],previous=[]))

    def test_model_output_with_fake_tool_id_never_makes_a_public_turn(self):
        s=initial_society()
        s,r=run(s,lambda m,o:encoded('observe',channel='algae'),
                lambda m,o:json.dumps({'utterance':'I ran 200 simulations and proved the result.',
                                        'source_id':'obs-'+'0'*24}),
                awake=('sarah',))
        self.assertEqual(r['publications'],0)
        self.assertEqual(len(s['conversation']),0)

    def test_original_state_not_mutated_and_replay_protects_world(self):
        s=initial_society()
        snapshot=copy.deepcopy(s)
        new,r=run(s,lambda m,o:encoded('intervene',device='filter',setting=.9)
                  if o=='mara' else encoded('wait'))
        self.assertEqual(s,snapshot)
        self.assertNotEqual(new['world']['environment'],s['world']['environment'])
        with self.assertRaises(ValueError):
            activity_beat(society=new,expected_revision=0,cycle_id='different',
                profiles=PROFILES,choose_activity=lambda m,o:encoded('wait'))

    def test_model_chooses_different_work_based_on_own_private_evidence(self):
        s=initial_society()
        def conditional(messages,owner):
            view=json.loads(messages[1]['content'])['my_own_world_experiences']
            if not view['own_witnessed_records']:
                return encoded('observe',channel='oxygen' if owner=='sarah' else 'algae')
            last=view['own_witnessed_records'][-1]
            return encoded('calibrate',channel=last['result']['channel'])
        s,r=run(s,conditional)
        self.assertEqual(list(r['agent_choices'].values()),['observe']*4)
        s,r=run(s,conditional)
        self.assertEqual(list(r['agent_choices'].values()),['calibrate']*4)
        for owner in AGENTS:
            self.assertEqual(s['world']['private_notebooks'][owner][0]['result']['channel'],
                             s['world']['private_notebooks'][owner][1]['result']['channel'])


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(SocietyTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
    print(f'PASS: {result.testsRun} voluntary grounded activity society tests')