#!/usr/bin/env python3
"""Twelve-beat real-model test of independent consequential activity.

Unlike short model-selection probes, this holds the simulated world and each
owner's notebook across many choices. The local 3B chooses operations and may
independently produce cited speech; no automated novelty, speaking schedule,
topic switch or mandatory action is inserted. Strictly research-only.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from room_endogenous_activity_3b_canary import _profiles, SPEECH_SCHEMA
from room_endogenous_activity_society import initial_society, activity_beat
from room_endogenous_activity_menu import (
    menu_messages, menu_response_schema, parse_menu_choice, encode_tool_plan,
)


def evaluate(config, tool_request, speech_request, *, beats=12, seed='holdout-activity-b',
             on_checkpoint=None):
    if type(beats) is not int or not 2<=beats<=16:
        raise ValueError('invalid bounded research horizon')
    if not isinstance(seed,str) or not seed.startswith('holdout-activity-'):
        raise ValueError('research holdout seed required')
    profiles=_profiles(config)
    society=initial_society(seed)
    records=[]
    started=time.monotonic()
    for i in range(beats):
        before=society['world']['environment']
        failures=[]
        def plan(messages,owner):
            try:
                menu=menu_messages(owner=owner,profile=profiles[owner],
                                   world=society['world'])
                response=tool_request(menu,33.0,
                                      menu_response_schema(society['world'],owner))
                return encode_tool_plan(parse_menu_choice(
                    response,society['world'],owner))
            except Exception:
                failures.append(owner+':action_model_unavailable')
                return None
        def speech(messages,owner):
            try:
                return speech_request(messages,33.0)
            except Exception:
                failures.append(owner+':speech_model_unavailable')
                return None
        society,info=activity_beat(
            society=society,expected_revision=society['revision'],
            cycle_id=f'holdout-{i+1}',profiles=profiles,
            choose_activity=plan,choose_speech=speech,
            awake=('sarah','jules'),speech_budget=1)
        changes=sum(abs(before[k]-society['world']['environment'][k])>1e-6
                    for k in ('oxygen','temperature','algae','turbidity'))
        record={
            'tick':info['world_tick'],
            'owner_choices':info['agent_choices'],
            'verified_private_experiments':info['new_receipts'],
            'explicit_evidence_shares':info['new_shared_evidence'],
            'physical_control_changes':info['control_changes'],
            'simulated_quantities_changed':changes,
            'published_research_speech':info['publications'],
            'model_calls':info['model_calls'],
            'errors':info['model_failures']+failures,
        }
        records.append(record)
        if on_checkpoint is not None:
            on_checkpoint(records,society)
    actions=[a for r in records for a in r['owner_choices'].values() if a!='wait']
    participants={a for r in records for a,k in r['owner_choices'].items() if k!='wait'}
    receipts=sum(r['verified_private_experiments'] for r in records)
    published=sum(r['published_research_speech'] for r in records)
    diversity=len(set(actions))
    cost=round(time.monotonic()-started,2)
    # A strict evaluation condition, not a goal disclosed to the model.
    quality=receipts>=5 and diversity>=2 and len(participants)>=2
    return {
        'experiment':'room_3b_long_horizon_consequential_activity',
        'mode':'isolated_synthetic_holdout',
        'model':'Llama-3.2-3B-Instruct',
        'seed_fingerprint':hashlib.sha256(seed.encode()).hexdigest()[:16],
        'beats':records,
        'summary':{
            'completed_beats':len(records),
            'verified_private_experiments':receipts,
            'distinct_computational_actions':diversity,
            'different_active_owners':len(participants),
            'explicit_evidence_shares':sum(r['explicit_evidence_shares'] for r in records),
            'real_world_control_changes':sum(r['physical_control_changes'] for r in records),
            'accepted_source_grounded_speech':published,
            'completely_silent_beats':sum(r['published_research_speech']==0 for r in records),
            'model_calls':sum(r['model_calls'] for r in records),
            'elapsed_seconds':cost,
            'seconds_per_beat':round(cost/len(records),2),
            'real_model_independent_activity_gate':quality,
            'independently_validated_human_likeness':False,
            'ready_for_live':False,
        },
        'final_environment_hash':hashlib.sha256(json.dumps(
            society['world']['environment'],sort_keys=True).encode()).hexdigest()[:20],
        'changed_live_main':False,
        'published_dialogue':False,
        'called_viewer_relay':False,
    }


def main():
    from room_endogenous_schema_transport import local_grammar_request
    a=argparse.ArgumentParser()
    a.add_argument('--model-url',required=True)
    a.add_argument('--config',default='room/config.json')
    a.add_argument('--beats',type=int,default=12)
    a.add_argument('--out',default='room-activity-holdout-long3b.json')
    args=a.parse_args()
    profile=json.loads(Path(args.config).read_text(encoding='utf-8'))
    def tool(messages,timeout,schema):
        return local_grammar_request(
            endpoint=args.model_url,schema=schema,
            n_predict=70,temperature=.43)(messages,timeout)
    speak=local_grammar_request(endpoint=args.model_url,
                               schema=SPEECH_SCHEMA,
                               n_predict=160,temperature=.42)
    def checkpoint(rows,society):
        data={'mode':'partial_research_only','finished':False,
              'completed_beats':len(rows),'beats':rows,
              'research_world_revision':society['world']['revision'],
              'ready_for_live':False}
        Path(args.out).write_text(json.dumps(data,sort_keys=True,indent=2)+'\n',
                                  encoding='utf-8')
        print(f'Completed real-model research tick {len(rows)}/{args.beats}',flush=True)
    result=evaluate(profile,tool,speak,beats=args.beats,on_checkpoint=checkpoint)
    Path(args.out).write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',
                              encoding='utf-8')
    print(json.dumps(result,sort_keys=True,indent=2))
    if not result['summary']['real_model_independent_activity_gate']:
        print('BLOCKED: heldout autonomous tool-use diversity/provenance insufficient',file=sys.stderr)
        return 2
    return 0


if __name__=='__main__':
    sys.exit(main())
