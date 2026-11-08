#!/usr/bin/env python3
"""Pinned Llama 3B: model-authored private investigation -> later action.

A goal can arise only after its owner actually ran a simulated experiment.
The same owner's journal is passed to later model tool decisions. The world
changes without chat. No mandatory novelty/action, scripted goals, live writes,
real laboratory claims, or ungrounded public speech.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
from pathlib import Path
from room_endogenous_activity_world import agent_view
from room_endogenous_activity_society import initial_society, activity_beat
from room_endogenous_activity_goals import current_goal
from room_endogenous_activity_menu import (
    menu_messages, menu_response_schema, parse_menu_choice, encode_tool_plan,
)
from room_endogenous_activity_3b_canary import _profiles, SPEECH_SCHEMA


def evaluate(config, activity_model, goal_model, speech_model, *, beats=4):
    if type(beats) is not int or not 2 <= beats <= 6:
        raise ValueError('bounded goal experiment duration')
    profiles=_profiles(config)
    state=initial_society('room-private-investigation-real3b')
    records=[]
    started=time.monotonic()
    for n in range(beats):
        previously={owner:current_goal(state['private_goals'][owner],owner)
                    for owner in ('sarah','jules')}
        def plan(messages,owner):
            menu=menu_messages(owner=owner,profile=profiles[owner],
                               world=state['world'],
                               personal_goal=previously[owner])
            schema=menu_response_schema(state['world'],owner)
            raw=activity_model(menu,33.0,schema)
            return encode_tool_plan(parse_menu_choice(raw,state['world'],owner))
        def goal(messages,owner):
            return goal_model(messages,30.0)
        def speech(messages,owner):
            return speech_model(messages,33.0)
        state,report=activity_beat(
            society=state,expected_revision=state['revision'],
            cycle_id=f'internal-goal-{n+1}',profiles=profiles,
            choose_activity=plan,choose_goal=goal,choose_speech=speech,
            awake=('sarah','jules'),speech_budget=1)
        new={owner:current_goal(state['private_goals'][owner],owner)
             for owner in ('sarah','jules')}
        records.append({
            'tick':report['world_tick'],
            'own_model_actions':report['agent_choices'],
            'model_calls':report['model_calls'],
            'verified_private_experiments':report['new_receipts'],
            'model_eligible_to_form_goal':report['private_goal_attempts'],
            'model_authored_private_goal':report['new_self_authored_goals'],
            'characters_with_active_owned_investigation':sum(bool(x) for x in new.values()),
            'independent_goal_used_next_decision':{
                owner:bool(previously[owner]) and report['agent_choices'].get(owner)!='wait'
                for owner in ('sarah','jules')},
            'source_grounded_public_contributions':report['publications'],
            'failure_count':len(report['model_failures']),
        })
    goal_total=sum(row['model_authored_private_goal'] for row in records)
    later=sum(sum(row['independent_goal_used_next_decision'].values()) for row in records)
    receipts=sum(row['verified_private_experiments'] for row in records)
    speak=sum(row['source_grounded_public_contributions'] for row in records)
    qualifies=goal_total>=1 and later>=1 and receipts>=2
    return {
        'experiment':'room_real3b_private_investigation_to_action',
        'mode':'synthetic_private_experiment_with_persistent_goals',
        'model':'Llama-3.2-3B-Instruct',
        'beats':records,
        'summary':{
            'completed_beats':beats,
            'verified_owner_private_experiments':receipts,
            'new_model_authored_private_goals':goal_total,
            'future_self_selected_actions_with_prior_own_goal':later,
            'verified_source_linked_public_contributions':speak,
            'world_advanced_without_conversation':all(r['tick']==i+1 for i,r in enumerate(records)),
            'elapsed_seconds':round(time.monotonic()-started,2),
            'model_calls':sum(r['model_calls'] for r in records),
            'internal_goal_to_future_action_demonstrated':qualifies,
            'causal_effect_of_goal_not_proven_by_this_trial':True,
            'long_horizon_human_social_naturalness_proven':False,
            'ready_for_live':False,
        },
        'live_room_changed':False,'real_feed_published':False,'viewer_relay_called':False,
    }


def main():
    from room_endogenous_schema_transport import local_grammar_request
    from room_endogenous_shadow import local_model_request
    p=argparse.ArgumentParser()
    p.add_argument('--model-url',required=True)
    p.add_argument('--config',default='room/config.json')
    p.add_argument('--beats',type=int,default=4)
    p.add_argument('--out',default='room-private-investigation-real3b.json')
    args=p.parse_args()
    config=json.loads(Path(args.config).read_text(encoding='utf-8'))
    def choose(messages,timeout,schema):
        return local_grammar_request(endpoint=args.model_url,schema=schema,
                n_predict=70,temperature=.45)(messages,timeout)
    think=local_model_request(endpoint=args.model_url,max_tokens=95,temperature=.47)
    speak=local_grammar_request(endpoint=args.model_url,schema=SPEECH_SCHEMA,
                               n_predict=155,temperature=.42)
    report=evaluate(config,choose,think,speak,beats=args.beats)
    Path(args.out).write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,sort_keys=True,indent=2))
    if not report['summary']['internal_goal_to_future_action_demonstrated']:
        print('BLOCKED: real 3B self-authored goal did not persist into new action',file=sys.stderr)
        return 2
    return 0


if __name__=='__main__':
    sys.exit(main())
