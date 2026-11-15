#!/usr/bin/env python3
"""Crash recovery, CAS, ownership and production-path avoidance tests."""
from __future__ import annotations
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from room_endogenous_activity_society import initial_society, activity_beat
from room_endogenous_activity_store import commit_activity,read_activity


def waiting_request(messages,owner):
    return json.dumps({'kind':'wait','channel':'','device':'','setting':0,
                       'horizon':1,'control':'current','window':2,'source_id':''})


def evolve(state,cycle):
    return activity_beat(society=state,expected_revision=state['revision'],
                         cycle_id=cycle,
                         profiles={x:{'core_identity':x} for x in ('sarah','mara','owen','jules')},
                         choose_activity=waiting_request,choose_speech=None)[0]


class StoreTests(unittest.TestCase):
    def test_durable_across_multiple_restarts(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'research-living-world.json'
            state=initial_society('restart')
            for i in range(1,31):
                state=evolve(state,f'beat-{i}')
                commit_activity(file,expected_revision=i-1,candidate=state,cycle_id=f'beat-{i}')
                state=read_activity(file)
            self.assertEqual(state['world']['tick'],30)
            self.assertEqual(read_activity(file),state)
            self.assertEqual(state['conversation'],[])

    def test_model_authored_investigation_survives_atomic_file_restart(self):
        from room_endogenous_activity_goals import current_goal
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'research-owner-investigations.json'
            base=initial_society('goal-restart')
            selected=lambda m,o: (
                json.dumps({'kind':'observe','channel':'oxygen','device':'',
                            'setting':0,'horizon':1,'control':'current',
                            'window':2,'source_id':''})
                if o=='mara' else waiting_request(m,o))
            state,report=activity_beat(
                society=base,expected_revision=0,cycle_id='first-owner-goal',
                profiles={x:{'core_identity':x} for x in ('sarah','mara','owen','jules')},
                choose_activity=selected, choose_speech=None,
                choose_goal=lambda m,o:'I want to compare oxygen measurements to a calibration reference.',
                awake=('mara','owen'))
            self.assertEqual(report['new_self_authored_goals'],1)
            commit_activity(path,expected_revision=0,candidate=state,cycle_id='first-owner-goal')
            recovered=read_activity(path)
            self.assertEqual(recovered['private_goals']['mara'],state['private_goals']['mara'])
            self.assertIn('oxygen',current_goal(recovered['private_goals']['mara'],'mara'))
            self.assertIsNone(recovered['private_goals']['owen']['current'])
            self.assertEqual(recovered['conversation'],[])
            second=evolve(recovered,'second-cycle')
            commit_activity(path,expected_revision=1,candidate=second,cycle_id='second-cycle')
            self.assertEqual(read_activity(path)['private_goals']['mara'],
                             recovered['private_goals']['mara'])

    def test_same_committed_cycle_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/'research-state.json'
            first=evolve(initial_society(),'beat-1')
            commit_activity(f,expected_revision=0,candidate=first,cycle_id='beat-1')
            copy=commit_activity(f,expected_revision=0,candidate=first,cycle_id='beat-1')
            self.assertEqual(copy,first)

    def test_stale_writer_rejected_without_changing_state(self):
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'research-state.json'
            first=evolve(initial_society(),'beat-1')
            commit_activity(file,expected_revision=0,candidate=first,cycle_id='beat-1')
            bad=evolve(initial_society(),'alternative-beat')
            with self.assertRaises(ValueError):
                commit_activity(file,expected_revision=0,candidate=bad,cycle_id='alternative-beat')
            self.assertEqual(read_activity(file),first)

    def test_crash_after_fsync_before_replace_preserves_old_state(self):
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/'research-state.json'
            first=evolve(initial_society(),'beat-1')
            commit_activity(f,expected_revision=0,candidate=first,cycle_id='beat-1')
            before=f.read_bytes()
            second=evolve(first,'beat-2')
            with patch('room_endogenous_activity_store.os.replace',side_effect=OSError('simulated failure')):
                with self.assertRaises(OSError):
                    commit_activity(f,expected_revision=1,candidate=second,cycle_id='beat-2')
            self.assertEqual(f.read_bytes(),before)
            self.assertEqual(read_activity(f),first)

    def test_refuses_overwrite_live_room_data(self):
        state=evolve(initial_society(),'beat-1')
        with tempfile.TemporaryDirectory() as folder:
            for f in (Path(folder)/'room'/'feed.json',Path(folder)/'room'/'state.json',
                      Path(folder)/'live.json',Path(folder)/'room'/'activity.json'):
                with self.assertRaises(ValueError):
                    commit_activity(f,expected_revision=0,candidate=state,cycle_id='beat-1')


if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(StoreTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful(): raise SystemExit(1)
    print(f'PASS: {result.testsRun} crash-safe persistent activity world tests')