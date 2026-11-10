"""Isolated A/B/A causal attribution harness tests without a live model."""
import json
from room_endogenous_activity_evidence_aba_canary import fixtures,evaluate

CONFIG={'p':{'sarah':{'psychology_v2':{
    'core_identity':'Researches changes in numerical ecological systems.'}}}}


def state_sensitive_fixture(messages,timeout,schema):
    context=json.loads(messages[1]['content'])
    observation=context['my_own_world_experiences']['own_witnessed_records'][-1]
    channel=observation['result']['channel']
    choice='forecast:shade:'+channel+':4'
    assert choice in schema['properties']['choice']['enum']
    return json.dumps({'choice':choice})


def test_two_private_experiments_produce_same_external_conditions():
    states=fixtures()
    assert states['A']['environment']==states['B']['environment']
    assert states['A']['private_notebooks']['sarah'][0]['result']['channel']=='oxygen'
    assert states['B']['private_notebooks']['sarah'][0]['result']['channel']=='algae'


def test_synthetic_state_sensitive_policy_reproduces_aba():
    report=evaluate(CONFIG,state_sensitive_fixture)
    summary=report['summary']
    assert summary['valid_all']
    assert summary['original_choice_reproduced']
    assert summary['different_private_experiment_changed_action']
    assert not summary['independent_social_intelligence_proven']


def test_inert_policy_cannot_pass_private_causality_gate():
    report=evaluate(CONFIG,lambda m,t,s: json.dumps({'choice':'wait'}))
    assert report['summary']['valid_all']
    assert report['summary']['original_choice_reproduced']
    assert not report['summary']['different_private_experiment_changed_action']


def test_out_of_menu_model_actions_fail_closed():
    report=evaluate(CONFIG,lambda m,t,s: json.dumps({'choice':'read_peers_secrets'}))
    assert not report['summary']['valid_all']
    assert not report['summary']['different_private_experiment_changed_action']
    assert report['published_dialogue'] is False


if __name__=='__main__':
    tests=[v for k,v in sorted(globals().copy().items()) if k.startswith('test_') and callable(v)]
    for test in tests:test()
    print(f'PASS: {len(tests)} private-experiment A/B/A attribution tests')
