#!/usr/bin/env python3
"""Isolated real 3B activity-world canary: own tool choice -> real simulation.

No live Room imports, no main branch writes, no user feed, no relay. Two
participants get independent choices; optional speech is accepted only when
linked to an actual computed receipt. Aggregate metadata are reported;
private prompts, real-world usernames and raw dialogue are not logged.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from room_endogenous_activity_world import (
    AGENTS, available_action_schema, parse_activity_choice, activity_messages,
)
from room_endogenous_activity_society import initial_society, activity_beat

SPEECH_SCHEMA={
    'type':'object',
    'properties':{'utterance':{'type':'string'},'source_id':{'type':'string'}},
    'required':['utterance','source_id'],'additionalProperties':False,
}


def _profiles(config):
    base=config.get('p') or {}
    if not isinstance(base,dict):
        raise ValueError('missing configured Room identities')
    ret={}
    for who in ('sarah','jules'):
        if not isinstance(base.get(who),dict):
            raise ValueError('missing '+who+' profile')
        psych=base[who].get('psychology_v2') or {}
        ret[who]={'core_identity':str(psych.get('core_identity') or '')[:340]}
    return ret


def experiment(config, action_request, speech_request, beats=3):
    if not 1<=beats<=5:
        raise ValueError('invalid trial duration')
    profiles=_profiles(config)
    state=initial_society('research-real3b-activity-20261108')
    reports=[]
    started=time.monotonic()
    for i in range(beats):
        before=state['world']['environment']
        failures=[]
        def plan(messages, owner):
            try:
                return action_request(messages,33.0)
            except Exception:
                failures.append(owner+':action_unavailable')
                return None
        def speech(messages, owner):
            try:
                return speech_request(messages,33.0)
            except Exception:
                failures.append(owner+':speech_unavailable')
                return None
        state, report=activity_beat(
            society=state, expected_revision=state['revision'],
            cycle_id=f'research-3b-{i+1}', profiles=profiles,
            choose_activity=plan, choose_speech=speech,
            awake=('sarah','jules'), speech_budget=1)
        changed=sum(abs(before[k]-state['world']['environment'][k])>1e-6
                    for k in ('oxygen','temperature','algae','turbidity'))
        reports.append({'tick':report['world_tick'],
                        'self_chosen_actions':report['agent_choices'],
                        'new_private_computed_records':report['new_receipts'],
                        'new_witnessed_shared_evidence':report['new_shared_evidence'],
                        'control_changes':report['control_changes'],
                        'environment_values_changed':changed,
                        'model_calls':report['model_calls'],
                        'valid_grounded_public_candidate':report['publications'],
                        'model_failures':report['model_failures']+failures})
    kinds=[v for x in reports for v in x['self_chosen_actions'].values() if v!='wait']
    receipts=sum(x['new_private_computed_records'] for x in reports)
    publications=sum(x['valid_grounded_public_candidate'] for x in reports)
    return {
        'experiment':'room_real3b_environment_first_activity_v1',
        'mode':'synthetic_numerical_environment_read_only',
        'model':'Llama-3.2-3B-Instruct',
        'turns':reports,
        'summary':{
            'ticks':beats,
            'different_world_variables_changed_each_tick':all(x['environment_values_changed']>=2 for x in reports),
            'model_chose_computational_actions':len(kinds),
            'distinct_computational_actions':len(set(kinds)),
            'verified_private_receipts':receipts,
            'model_created_grounded_public_speech':publications,
            'genuine_silence_allowed':True,
            'model_inference_calls':sum(x['model_calls'] for x in reports),
            'elapsed_seconds':round(time.monotonic()-started,2),
            'computational_agency_observed':receipts>=2 and len(set(kinds))>=2,
            'human_like_social_behavior_proven':False,
            'ready_for_live':False,
        },
        'published_dialogue':False,
        'changed_live_main':False,
        'called_viewer_relay':False,
        'wrote_private_live_memory':False,
    }


def main():
    from room_endogenous_schema_transport import local_grammar_request
    p=argparse.ArgumentParser()
    p.add_argument('--model-url',required=True)
    p.add_argument('--config',default='room/config.json')
    p.add_argument('--out',default='room-activity-real3b-canary.json')
    p.add_argument('--beats',type=int,default=3)
    args=p.parse_args()
    config=json.loads(Path(args.config).read_text(encoding='utf-8'))
    tool=local_grammar_request(endpoint=args.model_url,schema=available_action_schema(),
                               n_predict=170,temperature=.42)
    speech=local_grammar_request(endpoint=args.model_url,schema=SPEECH_SCHEMA,
                                 n_predict=170,temperature=.42)
    report=experiment(config,tool,speech,beats=args.beats)
    Path(args.out).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(report,sort_keys=True,indent=2))
    if not report['summary']['computational_agency_observed']:
        print('FAILED behavioral computational agency gate: model chose insufficient real work',file=sys.stderr)
        return 2
    return 0


if __name__=='__main__':
    sys.exit(main())