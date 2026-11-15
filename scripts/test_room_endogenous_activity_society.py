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
    def test_owned_goal_is_authored_after_experiment_and_guides_later_work(self):
        state=initial_society('own-self-investigation')
        observations=[]
        def self_chosen_action(messages,owner):
            ctx=json.loads(messages[1]['content'])
            if owner!='sarah':return encoded('wait')
            own=ctx['my_own_world_experiences']['own_witnessed_records']
            if not own:return encoded('observe',channel='oxygen')
            observations.append(ctx['individual_current_goal'])
            return encoded('calibrate',channel='oxygen') if (
                'sensor bias' in ctx['individual_current_goal']) else encoded('wait')
        goal_calls=[]
        def choose_goal(messages,owner):
            goal_calls.append(owner)
            assert owner=='sarah'
            assert 'own_witnessed_records' not in messages[1]['content']
            return 'I want to investigate whether oxygen sensor bias explains my reading.'
        first, report=activity_beat(
            society=state, expected_revision=0, cycle_id='first',
            profiles=PROFILES, choose_activity=self_chosen_action,
            choose_speech=None, choose_goal=choose_goal,
            awake=('sarah','jules'))
        self.assertEqual(first['world']['tick'],1)
        self.assertEqual(report['new_self_authored_goals'],1)
        self.assertEqual(report['private_goal_attempts'],1)
        self.assertEqual(goal_calls,['sarah'])
        self.assertEqual(first['conversation'],[])
        owned=first['private_goals']['sarah']
        self.assertEqual(owned['owner'],'sarah')
        self.assertEqual(owned['current']['source_id'],
                         first['world']['private_notebooks']['sarah'][-1]['id'])
        self.assertIsNone(first['private_goals']['jules']['current'])
        second, report=activity_beat(
            society=first, expected_revision=1, cycle_id='second',
            profiles=PROFILES, choose_activity=self_chosen_action,
            choose_speech=None, awake=('sarah','jules'))
        self.assertEqual(report['agent_choices']['sarah'],'calibrate')
        self.assertEqual(second['world']['private_notebooks']['sarah'][-1]['kind'],'calibrate')
        self.assertTrue(any('sensor bias' in x for x in observations))
        self.assertEqual(second['private_goals']['sarah'],owned)
        self.assertEqual(state['private_goals']['sarah']['revision'],0)

    def test_goal_model_no_goal_and_failure_never_trigger_speech_or_fake_actions(self):
        for response in ('[NO_GOAL]',None):
            state=initial_society('private-decline')
            def voluntary_no_goal(messages,owner):
                if response is None:raise TimeoutError('private goal model offline')
                return response
            next_,report=activity_beat(
                society=state, expected_revision=0, cycle_id='private-idle',
                profiles=PROFILES, choose_activity=lambda m,o:(
                    encoded('observe',channel='oxygen') if o=='sarah' else encoded('wait')),
                choose_goal=voluntary_no_goal, choose_speech=None,
                awake=('sarah','jules'))
            self.assertEqual(report['new_self_authored_goals'],0)
            self.assertEqual(report['private_goal_attempts'],1)
            self.assertIsNone(next_['private_goals']['sarah']['current'])
            self.assertEqual(next_['conversation'],[])
            self.assertEqual(report['new_receipts'],1)

    def test_direct_external_goal_injection_cannot_override_model_owned_work(self):
        state=initial_society()
        with self.assertRaises(ValueError):
            activity_beat(
                society=state,expected_revision=0,cycle_id='no-imposed-goals',
                profiles=PROFILES,choose_activity=lambda m,o:encoded('wait'),
                goals={'sarah':'You must speak about labyrinths.'})
        self.assertEqual(state['world']['tick'],0)

    def test_same_private_goal_cycle_replay_does_not_infer_again(self):
        state=initial_society()
        def choose(messages,owner):
            return encoded('observe',channel='oxygen') if owner=='sarah' else encoded('wait')
        first,report=activity_beat(
            society=state,expected_revision=0,cycle_id='replay-goal',
            profiles=PROFILES,choose_activity=choose,
            choose_goal=lambda m,o:'I want to investigate the oxygen trend.',
            awake=('sarah',),choose_speech=None)
        self.assertEqual(report['new_self_authored_goals'],1)
        def explode(*args):raise AssertionError('replayed private inference')
        repeated,rec=activity_beat(
            society=first,expected_revision=0,cycle_id='replay-goal',
            profiles=PROFILES,choose_activity=explode,
            choose_goal=explode,awake=('sarah',))
        self.assertEqual(first,repeated)
        self.assertTrue(rec['replayed'])
        self.assertEqual(rec['model_calls'],0)

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

    def test_hallucinated_foreign_share_cannot_stop_ongoing_world(self):
        state=initial_society()
        state,_=run(state,lambda m,o:encoded('observe',channel='algae')
                    if o=='jules' else encoded('wait'))
        private_id=state['world']['private_notebooks']['jules'][0]['id']
        before=state['world']['environment'].copy()
        def bad_share(messages, owner):
            if owner=='sarah':
                return encoded('share', source_id=private_id)
            if owner=='mara':
                return encoded('observe', channel='oxygen')
            return encoded('wait')
        state,report=run(state,bad_share)
        self.assertEqual(state['world']['tick'],2)
        self.assertNotEqual(state['world']['environment'],before)
        self.assertEqual(report['new_receipts'],1)
        self.assertEqual(report['agent_choices']['sarah'],'wait')
        self.assertIn('sarah:foreign_or_missing_evidence',report['model_failures'])
        self.assertEqual(state['world']['public_evidence'],[])
        self.assertEqual(state['world']['private_notebooks']['sarah'],[])

    def test_no_private_peer_claim_may_hide_in_source_linked_speech(self):
        state=initial_society()
        state,_=run(state,lambda m,o:encoded('observe',channel='oxygen')
                    if o=='sarah' else encoded('wait'))
        own_id=state['world']['private_notebooks']['sarah'][0]['id']
        candidate=json.dumps({'utterance':"Mara's private hypothesis has changed overnight.",
                              'source_id':own_id})
        self.assertIsNone(parse_voluntary_speech(
            candidate,owner='sarah',world=state['world'],previous=[]))

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

    def test_shared_discovery_changes_another_agents_possible_work(self):
        # A synthetic policy explicitly chooses each action. This verifies
        # the social physics, NOT autonomous initiative by a real model.
        society=initial_society('shared-evidence-scenario')
        society,first=run(society,
            lambda msgs,owner:encoded('observe',channel='oxygen')
            if owner=='jules' else encoded('wait'))
        original=society['world']['private_notebooks']['jules'][-1]['id']
        self.assertEqual(len(society['world']['public_evidence']),0)
        society,second=run(society,
            lambda msgs,owner:encoded('share',source_id=original)
            if owner=='jules' else encoded('wait'))
        self.assertEqual(second['new_shared_evidence'],1)
        def following(messages,owner):
            context=json.loads(messages[1]['content'])
            shared=context['my_own_world_experiences']['shared_computed_evidence']
            if owner=='sarah' and shared:
                return encoded('forecast',channel='oxygen',horizon=4,control='filter')
            return encoded('wait')
        def voluntary_speech(messages,owner):
            if owner!='sarah': return SILENCE
            context=json.loads(messages[1]['content'])
            own=context['my_experiences']['own_witnessed_records']
            if not own: return SILENCE
            latest=own[-1]
            difference=latest['result']['difference']
            return json.dumps({'utterance':
                    f'I calculated a simulated oxygen difference of {difference} units under filtration.',
                    'source_id':latest['id']})
        society,third=run(society,following,voluntary_speech,budget=4)
        self.assertEqual(third['new_receipts'],1)
        self.assertEqual(third['publications'],1)
        self.assertEqual(society['conversation'][-1]['speaker'],'sarah')
        self.assertEqual(society['world']['private_notebooks']['mara'],[])
        self.assertEqual(society['world']['public_evidence'][0]['source_id'],original)
        self.assertEqual(society['world']['private_notebooks']['sarah'][-1]['kind'],'forecast')
        self.assertNotIn(original,[v['id'] for v in
                         society['world']['private_notebooks']['sarah']])

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