#!/usr/bin/env python3
"""The model owns its activity choice but cannot submit out-of-world programs."""
import json
import unittest
from room_endogenous_activity_menu import available_choices,menu_messages,menu_response_schema,parse_menu_choice
from room_endogenous_activity_world import initial_world,advance_world


class MenuTests(unittest.TestCase):
    def test_menu_contains_real_work_and_unforced_wait(self):
        w=initial_world()
        choices=available_choices(w,'sarah')
        self.assertEqual(choices['wait'],{'kind':'wait'})
        self.assertIn('observe:oxygen',choices)
        self.assertIn('forecast:shade:oxygen:4',choices)
        self.assertIn('intervene:filter:1',choices)
        self.assertIn('calibrate:temperature',choices)
        self.assertEqual(len(menu_response_schema(w,'sarah')['required']),1)

    def test_exact_independent_action_resolves_to_verifiable_world_choice(self):
        w=initial_world()
        proposal=parse_menu_choice('{"choice":"intervene:shade:1"}',w,'jules')
        self.assertEqual(proposal,{'kind':'intervene','device':'shade','setting':1.0})
        w,report=advance_world(w,expected_revision=0,cycle_id='one',proposals={'jules':proposal})
        self.assertEqual(w['controls']['shade'],1.0)
        self.assertEqual(report['control_changes'],1)

    def test_invalid_response_is_wait_not_fake_action(self):
        w=initial_world()
        for raw in ('broken','{}','{"choice":"execute:arbitrary_python"}',
                    '{"choice":"observe:secret_private_memory"}',
                    '{"choice":"observe:oxygen","admin":true}'):
            self.assertEqual(parse_menu_choice(raw,w,'sarah'),{'kind':'wait'})

    def test_foreign_sources_cannot_be_shared_from_model_choice(self):
        w=initial_world()
        w,report=advance_world(w,expected_revision=0,cycle_id='one',
                               proposals={'mara':{'kind':'observe','channel':'oxygen'}})
        source=report['receipts'][0]['id']
        self.assertNotIn('share:'+source,available_choices(w,'sarah'))
        self.assertIn('share:'+source,available_choices(w,'mara'))
        self.assertEqual(parse_menu_choice(json.dumps({'choice':'share:'+source}),w,'sarah'),{'kind':'wait'})
        self.assertEqual(parse_menu_choice(json.dumps({'choice':'share:'+source}),w,'mara'),
                         {'kind':'share','source_id':source})

    def test_dynamic_model_prompt_contains_only_owner_experiences(self):
        w=initial_world()
        w,rep=advance_world(w,expected_revision=0,cycle_id='one',
                            proposals={'sarah':{'kind':'observe','channel':'algae'},
                                       'mara':{'kind':'observe','channel':'oxygen'}})
        msgs=menu_messages(owner='sarah',profile={'core_identity':'Causal scientist'},
                           world=w,personal_goal='Understand the algae response')
        ctx=json.loads(msgs[1]['content'])
        self.assertIn(rep['receipts'][1]['id'],json.dumps(ctx))
        self.assertNotIn(rep['receipts'][0]['id'],json.dumps(ctx))
        self.assertIn('wait',ctx['individual_action_menu'])
        self.assertIn('Understand the algae response',ctx['individual_current_goal'])


if __name__=='__main__':
    s=unittest.defaultTestLoader.loadTestsFromTestCase(MenuTests)
    r=unittest.TextTestRunner(verbosity=2).run(s)
    if not r.wasSuccessful():raise SystemExit(1)
    print(f'PASS: {r.testsRun} bounded owner-chosen experiment menu tests')