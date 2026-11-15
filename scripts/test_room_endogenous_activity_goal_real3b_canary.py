"""Verify evidence->owner-goal->future work before invoking expensive 3B."""
import json
from room_endogenous_activity_goal_real3b_canary import evaluate

CONFIG={'p':{
    'sarah':{'psychology_v2':{'core_identity':'Interested in physical system dynamics'}},
    'jules':{'psychology_v2':{'core_identity':'Interested in biological relationships'}},
}}


def model_choice(messages,timeout,schema):
    ctx=json.loads(messages[1]['content'])
    owner=ctx['agent']
    own=ctx['my_own_world_experiences']['own_witnessed_records']
    if not own:
        choice='observe:oxygen' if owner=='sarah' else 'observe:algae'
    else:
        choice='calibrate:oxygen' if owner=='sarah' else 'forecast:shade:algae:4'
    assert choice in schema['properties']['choice']['enum']
    return json.dumps({'choice':choice})


def no_public_model(messages,timeout):
    return '{"utterance":"","source_id":""}'


def test_private_goal_survives_and_is_present_in_next_model_action():
    seen_goals=[]
    def record_goal(request,timeout,schema):
        ctx=json.loads(request[1]['content'])
        seen_goals.append(ctx['individual_current_goal'])
        return model_choice(request,timeout,schema)
    def private_thought(msgs,timeout):
        ctx=json.loads(msgs[1]['content'])
        assert len(ctx['recent_private_verified_simulated_experiments'])>=1
        return 'I want to compare my simulated measurements with a reference instrument.'
    report=evaluate(CONFIG,record_goal,private_thought,no_public_model,beats=4)
    s=report['summary']
    assert s['verified_owner_private_experiments']==8
    assert s['new_model_authored_private_goals']>=1
    assert s['future_self_selected_actions_with_prior_own_goal']>=1
    assert s['internal_goal_to_future_action_demonstrated']
    assert any('compare my simulated' in x for x in seen_goals)
    assert not report['live_room_changed'] and not report['real_feed_published']


def test_no_goal_cannot_be_misreported_as_autonomous_goal_growth():
    s=evaluate(CONFIG,model_choice,lambda m,t:'[NO_GOAL]',
               no_public_model,beats=3)['summary']
    assert s['verified_owner_private_experiments']>=2
    assert s['new_model_authored_private_goals']==0
    assert s['future_self_selected_actions_with_prior_own_goal']==0
    assert not s['internal_goal_to_future_action_demonstrated']


def test_llm_failure_cannot_fabricate_activity_or_goal():
    def broken(*args): raise TimeoutError('offline 3B')
    s=evaluate(CONFIG,broken,broken,broken,beats=2)['summary']
    assert s['verified_owner_private_experiments']==0
    assert s['new_model_authored_private_goals']==0
    assert s['future_self_selected_actions_with_prior_own_goal']==0
    assert s['world_advanced_without_conversation']
    assert not s['internal_goal_to_future_action_demonstrated']


def test_research_horizon_is_strictly_bounded():
    for n in (0,-1,7,True):
        try:evaluate(CONFIG,model_choice,lambda *a:'[NO_GOAL]',no_public_model,beats=n)
        except ValueError:pass
        else:raise AssertionError('unbounded real model script')


if __name__=='__main__':
    tests=[v for k,v in sorted(globals().copy().items()) if k.startswith('test_') and callable(v)]
    for t in tests:t()
    print(f'PASS: {len(tests)} real-model owner investigations and future-work harness tests')
