#!/usr/bin/env python3
"""No model required. Long-horizon, causal, private, replay-safe world tests."""
from __future__ import annotations

import copy
import json
import math
import sys
import time
import unittest

from room_endogenous_activity_world import (
    AGENTS, CHANNELS, SCHEMA, MAX_CYCLES, MAX_HISTORY, MAX_NOTEBOOK,
    MAX_SHARED, _state_ok, advance_world, initial_world, agent_view,
    activity_messages, available_action_schema, parse_activity_choice,
)


def tick(world, proposals=None, cycle_id=None):
    return advance_world(
        world, expected_revision=world['revision'],
        cycle_id=cycle_id or f'beat-{world["tick"] + 1}', proposals=proposals or {})


class ActivityWorldTests(unittest.TestCase):
    def test_initial_state_independent_of_conversation(self):
        world = initial_world()
        self.assertEqual(world['tick'], 0)
        self.assertEqual(world['schema'], SCHEMA)
        self.assertTrue(_state_ok(world))
        self.assertEqual(set(world['private_notebooks']), set(AGENTS))
        self.assertEqual(world['public_evidence'], [])

    def test_world_keeps_changing_with_zero_dialogue_or_model_requests(self):
        world = initial_world()
        initial = dict(world['environment'])
        for t in range(1, 400):
            world, report = tick(world)
            self.assertEqual(world['tick'], t)
            self.assertEqual(report['new_receipts'], 0)
        self.assertNotEqual(initial['temperature'], world['environment']['temperature'])
        self.assertNotEqual(initial['oxygen'], world['environment']['oxygen'])
        self.assertTrue(_state_ok(world))
        self.assertEqual(world['public_evidence'], [])
        self.assertEqual(world['revision'], 399)
        self.assertLessEqual(len(world['history']), MAX_HISTORY)
        self.assertLessEqual(len(world['cycles']), MAX_CYCLES)
        self.assertTrue(all(world['private_notebooks'][name] == [] for name in AGENTS))

    def test_long_horizon_numerical_stability_and_bounded_memory(self):
        world = initial_world('long-horizon-seed')
        for _ in range(2500):
            world, _ = tick(world)
        self.assertTrue(_state_ok(world))
        self.assertEqual(world['revision'], 2500)
        self.assertLessEqual(len(world['events']), 32)
        for value in world['environment'].values():
            self.assertTrue(math.isfinite(value))
            self.assertGreaterEqual(value, 0)

    def test_determinism_reproducible_from_seed(self):
        a, b = initial_world('equal'), initial_world('equal')
        for _ in range(51):
            a, rep_a = tick(a)
            b, rep_b = tick(b)
            self.assertEqual(a, b)
            self.assertEqual(rep_a, rep_b)
        c = initial_world('different-seed')
        c, _ = tick(c)
        self.assertNotEqual(c['environment'], initial_world('equal')['environment'])

    def test_source_labeled_instrument_reading_is_real_simulated_computation(self):
        world = initial_world()
        next_state, report = tick(world, {'mara': {'kind':'observe','channel':'oxygen'}})
        self.assertEqual(report['new_receipts'], 1)
        note = next_state['private_notebooks']['mara'][-1]
        self.assertEqual(note['owner'], 'mara')
        self.assertEqual(note['kind'], 'observe')
        self.assertEqual(note['provenance'], 'computed_fictional_environment')
        self.assertEqual(note['tick'], 1)
        self.assertNotEqual(note['result']['reported'], world['environment']['oxygen'])
        self.assertEqual(next_state['private_notebooks']['sarah'], [])
        self.assertEqual(world['private_notebooks']['mara'], [])
        self.assertEqual(next_state['public_evidence'], [])

    def test_calibration_and_comparison_are_calculated_not_storytelling(self):
        w = initial_world()
        w, report = tick(w, {'sarah': {'kind':'calibrate','channel':'temperature'}})
        obj = report['receipts'][0]['result']
        self.assertAlmostEqual(obj['reported'] - obj['lab_reference'], obj['estimated_sensor_bias'], places=5)
        self.assertLess(abs(obj['lab_reference'] - w['environment']['temperature']), .009)
        self.assertEqual(obj['reference_status'], 'fictional_simulation_reference')

    def test_agent_controls_have_verifiable_delayed_environmental_effects(self):
        standard, test = initial_world('control-paired'), initial_world('control-paired')
        standard, _ = tick(standard)
        test, rep = tick(test, {'jules': {'kind':'intervene','device':'shade','setting':.95}})
        self.assertEqual(rep['control_changes'], 1)
        self.assertEqual(test['controls']['shade'], .95)
        self.assertEqual(test['environment']['temperature'] < standard['environment']['temperature'], True)
        for _ in range(8):
            standard, _ = tick(standard)
            test, _ = tick(test)
        self.assertLess(test['environment']['algae'], standard['environment']['algae'])
        self.assertNotEqual(test['environment']['oxygen'], standard['environment']['oxygen'])

    def test_filter_reduces_turbidity_but_consumes_energy(self):
        base, filtered = initial_world('filter-test'), initial_world('filter-test')
        for _ in range(10):
            base, _ = tick(base)
            filtered, _ = tick(filtered, {'owen':{'kind':'intervene','device':'filter','setting':.95}} if filtered['tick']==0 else {})
        self.assertLess(filtered['environment']['turbidity'], base['environment']['turbidity'])
        self.assertLess(filtered['environment']['energy'], base['environment']['energy'])

    def test_counterfactual_forecast_executes_real_deterministic_dynamics(self):
        a = initial_world('counterfactual-seed')
        b, report = tick(a, {'owen': {'kind':'forecast','channel':'temperature','horizon':8,'control':'shade'}})
        receipt = report['receipts'][0]['result']
        self.assertEqual(receipt['horizon'], 8)
        self.assertNotEqual(receipt['hypothetical'], receipt['current_controls'])
        self.assertEqual(receipt['epistemic_status'], 'simulated_counterfactual_not_witnessed')
        b0, _ = tick(a)
        self.assertEqual(b['environment'], b0['environment'])
        for _ in range(8):
            b0, _ = tick(b0)
        self.assertAlmostEqual(receipt['current_controls'], b0['environment']['temperature'])

    def test_trend_calculates_observed_data_not_random_text(self):
        w = initial_world()
        for _ in range(10):
            w, _ = tick(w)
        outcome, info = tick(w, {'jules': {'kind':'trend','channel':'algae','window':7}})
        data = [r['algae'] for r in outcome['history'][-7:]]
        slope = (data[-1]-data[0])/(len(data)-1)
        self.assertAlmostEqual(info['receipts'][0]['result']['slope_per_tick'], slope, places=5)

    def test_foreign_observations_never_leak_into_agent_context(self):
        w = initial_world()
        w, r = tick(w, {'sarah': {'kind':'observe','channel':'temperature'},
                       'mara': {'kind':'observe','channel':'turbidity'}})
        sarah = agent_view(w, 'sarah')
        mara = agent_view(w, 'mara')
        self.assertEqual(len(sarah['own_witnessed_records']), 1)
        self.assertEqual(len(mara['own_witnessed_records']), 1)
        self.assertNotIn(r['receipts'][0]['id'], json.dumps(sarah))
        self.assertNotIn(r['receipts'][1]['id'], json.dumps(mara))
        self.assertNotIn('\"environment\":', json.dumps(sarah))
        self.assertNotIn('\"environment\":', json.dumps(mara))

    def test_owner_can_voluntarily_share_an_actual_existing_receipt(self):
        w = initial_world()
        w, info = tick(w, {'mara': {'kind':'observe','channel':'oxygen'}})
        source = info['receipts'][0]['id']
        w, res = tick(w, {'mara': {'kind':'share','source_id': source}})
        self.assertEqual(res['new_public_evidence'], 1)
        self.assertEqual(w['public_evidence'][0]['source_id'], source)
        self.assertEqual(w['public_evidence'][0]['verified_result'], info['receipts'][0]['result'])
        w, res = tick(w, {'mara': {'kind':'share','source_id': source}})
        self.assertEqual(res['new_public_evidence'], 0)
        self.assertEqual(len(w['public_evidence']), 1)
        self.assertEqual(w['private_notebooks']['sarah'], [])
        self.assertEqual(agent_view(w, 'sarah')['shared_computed_evidence'][0]['source_id'], source)

    def test_foreign_or_invented_evidence_share_fails_entire_transaction(self):
        w = initial_world()
        w, info = tick(w, {'jules': {'kind':'observe','channel':'algae'}})
        prior = copy.deepcopy(w)
        bad = {'kind':'share','source_id': info['receipts'][0]['id']}
        with self.assertRaises(ValueError):
            tick(w, {'sarah': bad})
        with self.assertRaises(ValueError):
            tick(w, {'jules': {'kind':'share','source_id': 'obs-'+'a'*24}})
        self.assertEqual(w, prior)

    def test_simultaneous_conflicting_interventions_order_independent(self):
        w = initial_world()
        a, info_a = tick(w, {'sarah': {'kind':'intervene','device':'shade','setting':.4},
                             'mara': {'kind':'intervene','device':'shade','setting':.8}})
        b, info_b = tick(w, {'mara': {'kind':'intervene','device':'shade','setting':.8},
                             'sarah': {'kind':'intervene','device':'shade','setting':.4}})
        self.assertEqual(a, b)
        self.assertEqual(info_a, info_b)
        statuses = [x['result']['status'] for x in info_a['receipts']]
        self.assertEqual(sorted(statuses), ['committed', 'rejected'])

    def test_duplicate_idempotence_no_model_or_repeated_world_effect(self):
        w = initial_world()
        proposal = {'mara': {'kind':'intervene','device':'filter','setting':1.0}}
        first, info = tick(w, proposal, 'cycle-id-123')
        same, replay = advance_world(first, expected_revision=0, cycle_id='cycle-id-123', proposals=proposal)
        self.assertEqual(first, same)
        self.assertTrue(replay['replayed'])
        with self.assertRaises(ValueError):
            advance_world(first, expected_revision=1, cycle_id='cycle-id-123', proposals={})

    def test_revision_conflict_and_invalid_plan_do_not_advance_world(self):
        w = initial_world()
        with self.assertRaises(ValueError):
            advance_world(w, expected_revision=2, cycle_id='badrev', proposals={})
        for invalid in ({'sarah': {'kind':'intervene','device':'pump','setting':1}},
                        {'mara': {'kind':'forecast','channel':'oxygen','horizon':9999,'control':'current'}},
                        {'jules': {'kind':'intervene','device':'shade','setting': float('nan')}},
                        {'owen': {'kind':'execute_python','code':'rm -rf /'}}):
            with self.assertRaises(ValueError):
                tick(w, invalid)
            self.assertEqual(w['tick'], 0)

    def test_malformed_model_choice_always_falls_back_to_wait(self):
        for raw in ('', 'please change the filter', '{not-json', '{}',
                    '{"kind":"execute_python"}',
                    json.dumps({'kind':'observe','channel':'oxygen','admin_override':1}),
                    'x'*1500):
            self.assertEqual(parse_activity_choice(raw), {'kind':'wait'})
        plan={'kind':'forecast','channel':'oxygen','device':'','setting':0,
              'horizon':9,'control':'shade','window':2,'source_id':''}
        self.assertEqual(parse_activity_choice(json.dumps(plan)), {
            'kind':'forecast', 'channel':'oxygen','control':'shade','horizon':9})

    def test_private_model_request_includes_own_notebook_not_peer_notebook(self):
        w = initial_world()
        w, report = tick(w, {'sarah':{'kind':'observe','channel':'oxygen'},
                              'mara':{'kind':'observe','channel':'algae'}})
        request = activity_messages(owner='sarah',profile={'core_identity':'S synthesizer'},
                                    world=w,personal_goal='Examine the oxygen trend')
        text=json.dumps(request)
        # sorting by owner makes Mara's receipt the first, Sarah's the second.
        self.assertIn(report['receipts'][1]['id'], text)
        self.assertNotIn(report['receipts'][0]['id'], text)
        self.assertIn('Examine the oxygen trend', text)
        self.assertIn('wait', text)

    def test_state_roundtrip_is_stable_and_verifiable(self):
        w = initial_world('serialize-world')
        for _ in range(22):
            w, _ = tick(w)
        self.assertEqual(json.loads(json.dumps(w)), w)
        self.assertTrue(_state_ok(w))
        self.assertTrue(all(x['tick'] >= 0 for x in w['history']))


if __name__=='__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ActivityWorldTests)
    test = unittest.TextTestRunner(verbosity=2).run(suite)
    if not test.wasSuccessful():
        raise SystemExit(1)
    print(f'PASS: {test.testsRun} persistent independent activity world tests')