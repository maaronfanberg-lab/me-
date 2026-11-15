"""Offline holdout harness checks; these are not proof of model agency."""
import json
from room_endogenous_activity_long_3b_canary import evaluate

CONFIG={'p':{
    'sarah':{'psychology_v2':{'core_identity':'Study causal physical systems.'}},
    'jules':{'psychology_v2':{'core_identity':'Study adaptation and change.'}},
}}


def deterministic_fixture(messages,timeout,schema):
    context=json.loads(messages[1]['content'])
    owner=context['agent']
    own=context['my_own_world_experiences']['own_witnessed_records']
    if owner=='sarah':
        key='observe:oxygen' if not own else 'forecast:shade:oxygen:4'
    else:
        key='observe:algae' if not own else 'intervene:filter:0.5'
    assert key in schema['properties']['choice']['enum']
    return json.dumps({'choice':key})


def no_speech(*args):
    return json.dumps({'utterance':'','source_id':''})


def test_evolving_real_numeric_world_retains_owner_discoveries():
    checkpoints=[]
    report=evaluate(CONFIG,deterministic_fixture,no_speech,beats=4,
                    on_checkpoint=lambda rows,society:checkpoints.append((
                        len(rows),society['world']['revision'])))
    assert checkpoints==[(1,1),(2,2),(3,3),(4,4)]
    result=report['summary']
    assert result['completed_beats']==4
    assert result['verified_private_experiments']==8
    assert result['distinct_computational_actions']>=3
    assert result['different_active_owners']==2
    assert result['real_model_independent_activity_gate'] is True
    assert result['accepted_source_grounded_speech']==0
    assert report['changed_live_main'] is False


def test_dead_model_still_advances_world_without_fabricated_activity():
    def dead(*args): raise TimeoutError('model unavailable')
    report=evaluate(CONFIG,dead,dead,beats=3)
    result=report['summary']
    assert result['completed_beats']==3
    assert result['verified_private_experiments']==0
    assert result['real_model_independent_activity_gate'] is False
    assert result['model_calls']==6
    assert result['completely_silent_beats']==3


def test_all_wait_is_not_mislabeled_as_model_initiative():
    report=evaluate(CONFIG,lambda m,t,s:json.dumps({'choice':'wait'}),
                    no_speech,beats=4)
    assert report['summary']['verified_private_experiments']==0
    assert report['summary']['real_model_independent_activity_gate'] is False
    assert report['summary']['accepted_source_grounded_speech']==0


def test_bounded_horizon_fail_closed():
    for beats in (0,1,17,-3,True):
        try: evaluate(CONFIG,deterministic_fixture,no_speech,beats=beats)
        except ValueError: pass
        else: raise AssertionError('unbounded trial was accepted')


if __name__=='__main__':
    tests=[v for k,v in sorted(globals().copy().items()) if k.startswith('test_') and callable(v)]
    for fn in tests:fn()
    print(f'PASS: {len(tests)} long-horizon research 3B harness checks')
