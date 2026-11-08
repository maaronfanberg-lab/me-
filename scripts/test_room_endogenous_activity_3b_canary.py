#!/usr/bin/env python3
"""Canary instrumentation and readiness gates require actual executed actions."""
from __future__ import annotations
import json
import unittest
from room_endogenous_activity_3b_canary import experiment,_profiles,SPEECH_SCHEMA
from room_endogenous_activity_world import available_action_schema

CONFIG={'p':{
  'sarah':{'psychology_v2':{'core_identity':'Sarah is curious about system dynamics'}},
  'jules':{'psychology_v2':{'core_identity':'Jules explores biological adaptation'}}}}


def choice(kind='wait',**kwargs):
    data={'kind':kind,'channel':'','device':'','setting':0,
          'horizon':1,'control':'current','window':2,'source_id':''}
    data.update(kwargs)
    return json.dumps(data)


class CanaryTests(unittest.TestCase):
    def test_real_model_probe_with_model_chosen_operators(self):
        calls=[]
        def tools(messages,timeout):
            p=json.loads(messages[1]['content'])
            name=p['agent']
            calls.append(name)
            if not p['my_own_world_experiences']['own_witnessed_records']:
                return choice('observe',channel='oxygen' if name=='sarah' else 'algae')
            return choice('calibrate',channel='oxygen' if name=='sarah' else 'algae')
        result=experiment(CONFIG,tools,lambda *args: json.dumps({'utterance':'','source_id':''}),beats=2)
        self.assertEqual(result['summary']['model_chose_computational_actions'],4)
        self.assertEqual(result['summary']['distinct_computational_actions'],2)
        self.assertEqual(result['summary']['verified_private_receipts'],4)
        self.assertEqual(result['summary']['model_created_grounded_public_speech'],0)
        self.assertTrue(result['summary']['computational_agency_observed'])
        self.assertTrue(result['summary']['different_world_variables_changed_each_tick'])
        self.assertEqual(len(calls),4)
        self.assertFalse(result['changed_live_main'])

    def test_inert_model_cannot_fool_agency_gate(self):
        report=experiment(CONFIG,lambda m,t: choice('wait'),
                          lambda m,t:json.dumps({'utterance':'','source_id':''}),beats=2)
        self.assertFalse(report['summary']['computational_agency_observed'])
        self.assertEqual(report['summary']['verified_private_receipts'],0)
        self.assertEqual(report['summary']['ticks'],2)
        self.assertEqual(report['summary']['model_created_grounded_public_speech'],0)

    def test_action_model_failure_still_advances_world_without_fabricated_work(self):
        def broken(*_): raise TimeoutError('real 3B unavailable')
        report=experiment(CONFIG,broken,broken,beats=1)
        self.assertEqual(report['summary']['verified_private_receipts'],0)
        self.assertEqual(report['summary']['ticks'],1)
        self.assertTrue(report['summary']['different_world_variables_changed_each_tick'])
        self.assertFalse(report['summary']['computational_agency_observed'])

    def test_bounded_grammar_schemas_for_local_3b(self):
        schema=available_action_schema()
        self.assertEqual(len(schema['required']),8)
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(SPEECH_SCHEMA['required'],['utterance','source_id'])
        self.assertFalse(SPEECH_SCHEMA['additionalProperties'])


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(CanaryTests)
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    if not r.wasSuccessful():raise SystemExit(1)
    print(f'PASS: {r.testsRun} real 3B activity canary protocol tests')