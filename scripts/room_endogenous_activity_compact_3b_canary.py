#!/usr/bin/env python3
"""Separate real 3B compact-choice A/B instrument canary.

Unlike the concurrently evolving dynamic-menu trial, this one has a stable,
one-field action set and calls the checked society executor directly.
Every public candidate is model-authored and source-verified; no live writes.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from room_endogenous_activity_society import initial_society, activity_beat
from room_endogenous_activity_3b_canary import _profiles, SPEECH_SCHEMA
from room_endogenous_activity_compact import adapter, SCHEMA
from room_endogenous_schema_transport import local_grammar_request


def experiment_compact(config, tool_request, speech_request, *, beats=4):
    if type(beats) is not int or not 1 <= beats <= 5:
        raise ValueError('invalid experimental horizon')
    profiles=_profiles(config)
    state=initial_society('research-real3b-activity-20261108')
    records=[]
    started=time.monotonic()
    for i in range(beats):
        before=state['world']['environment']
        def choose(messages,owner):
            return tool_request(messages,33.0)
        def say(messages,owner):
            return speech_request(messages,33.0)
        state,report=activity_beat(
            society=state, expected_revision=state['revision'],
            cycle_id=f'compact-3b-{i+1}', profiles=profiles,
            choose_activity=choose, choose_speech=say,
            awake=('sarah','jules'),speech_budget=1)
        changed=sum(abs(before[k]-state['world']['environment'][k])>1e-6
                    for k in ('oxygen','temperature','algae','turbidity'))
        records.append({
            'tick':report['world_tick'],
            'self_chosen_actions':report['agent_choices'],
            'verified_private_receipts':report['new_receipts'],
            'witnessed_shared_evidence':report['new_shared_evidence'],
            'control_changes':report['control_changes'],
            'different_environment_values_changed':changed,
            'model_calls':report['model_calls'],
            'model_failures':report['model_failures'],
            'verified_public_speech':report['publications'],
        })
    actual=[k for r in records for k in r['self_chosen_actions'].values() if k!='wait']
    receipts=sum(r['verified_private_receipts'] for r in records)
    passed=receipts>=2 and len(set(actual))>=2
    return {
        'experiment':'room_real3b_compact_voluntary_activity_v1',
        'mode':'research_only_synthetic_numerical_world',
        'model':'Llama-3.2-3B-Instruct',
        'action_interface':'one_explicit_self_selected_instrument',
        'trials':records,
        'summary':{
            'ticks':beats,
            'model_chose_computational_actions':len(actual),
            'distinct_computational_actions':len(set(actual)),
            'verified_private_receipts':receipts,
            'verified_model_public_speech':sum(r['verified_public_speech'] for r in records),
            'world_evolved_each_beat':all(r['different_environment_values_changed']>=2 for r in records),
            'model_inference_calls':sum(r['model_calls'] for r in records),
            'elapsed_seconds':round(time.monotonic()-started,2),
            'computational_agency_observed':passed,
            'human_like_social_behavior_proven':False,
            'ready_for_live':False,
        },
        'changed_live_main':False,
        'published_dialogue':False,
        'called_viewer_relay':False,
        'wrote_private_live_memory':False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model-url',required=True)
    p.add_argument('--config',default='room/config.json')
    p.add_argument('--out',default='room-activity-compact-real3b.json')
    p.add_argument('--beats',type=int,default=4)
    a=p.parse_args()
    config=json.loads(Path(a.config).read_text(encoding='utf-8'))
    one_choice=local_grammar_request(endpoint=a.model_url,schema=SCHEMA,
                                     n_predict=62,temperature=.44)
    speech=local_grammar_request(endpoint=a.model_url,schema=SPEECH_SCHEMA,
                                 n_predict=160,temperature=.42)
    report=experiment_compact(config,adapter(one_choice),speech,beats=a.beats)
    Path(a.out).write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,sort_keys=True,indent=2))
    if not report['summary']['computational_agency_observed']:
        print('FAILED: real model chose insufficient independent verified work',file=sys.stderr)
        return 2
    return 0


if __name__=='__main__':
    sys.exit(main())
