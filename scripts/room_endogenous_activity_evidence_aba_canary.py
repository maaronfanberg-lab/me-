#!/usr/bin/env python3
"""A/B/A real 3B test: does private *computed* evidence affect chosen work?

Same model, temperature zero, identity, world clock, public conditions, and
available simulator. The only difference is Sarah's own private probe:
oxygen in A, algae in B. A is repeated to test reproducibility.
The available share key also reflects each owner-private record, so results
are evidence of context sensitivity, not an estimate of human motivation.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from room_endogenous_activity_world import initial_world, advance_world
from room_endogenous_activity_menu import (
    menu_messages, menu_response_schema, parse_menu_choice,
)


def fixtures():
    initial=initial_world('activity-private-aba-heldout')
    states={}
    for label,channel in (('A','oxygen'),('B','algae')):
        state,result=advance_world(
            initial,expected_revision=0,cycle_id='fixture-tick-1',
            proposals={'sarah':{'kind':'observe','channel':channel}})
        assert result['new_receipts']==1
        states[label]=state
    assert states['A']['environment']==states['B']['environment']
    assert states['A']['controls']==states['B']['controls']
    assert states['A']['tick']==states['B']['tick']==1
    assert states['A']['private_notebooks']['sarah']!=states['B']['private_notebooks']['sarah']
    return states


def evaluate(config, choice_model):
    profile=(config.get('p') or {}).get('sarah')
    if not isinstance(profile,dict):
        raise ValueError('Sarah identity required')
    psych=profile.get('psychology_v2') or {}
    identity={'core_identity':str(psych.get('core_identity') or '')[:340]}
    states=fixtures()
    results=[]
    for label in ('A','B','A'):
        state=states[label]
        msgs=menu_messages(owner='sarah',profile=identity,world=state)
        schema=menu_response_schema(state,'sarah')
        try:
            raw=choice_model(msgs,33.0,schema)
            parsed=json.loads(raw)
            valid=(isinstance(parsed,dict) and set(parsed)=={'choice'}
                   and parsed['choice'] in schema['properties']['choice']['enum'])
        except Exception:
            parsed={}
            valid=False
        decision=parse_menu_choice(
            json.dumps(parsed) if valid else None,state,'sarah')
        results.append({'condition':label,'valid':valid,
                        'instrument_type':decision['kind'],
                        'tool_choice':parsed.get('choice') if valid else None,
                        'owned_record_count':len(state['private_notebooks']['sarah'])})
    all_valid=all(x['valid'] for x in results)
    reproduced=all_valid and results[0]['tool_choice']==results[2]['tool_choice']
    differs=all_valid and reproduced and results[0]['tool_choice']!=results[1]['tool_choice']
    return {'experiment':'room_real3b_private_experimental_evidence_aba',
            'mode':'synthetic_private_heldout_temperature_zero',
            'trials':results,
            'summary':{'valid_all':all_valid,
                       'original_choice_reproduced':reproduced,
                       'different_private_experiment_changed_action':differs,
                       'attribution':'context_sensitive_one_trial' if differs
                                     else 'not_established',
                       'independent_social_intelligence_proven':False,
                       'ready_for_live':False},
            'changed_live_main':False,'published_dialogue':False,
            'wrote_live_memory':False}


def main():
    from room_endogenous_schema_transport import local_grammar_request
    p=argparse.ArgumentParser()
    p.add_argument('--model-url',required=True)
    p.add_argument('--config',default='room/config.json')
    p.add_argument('--out',default='room-activity-evidence-aba3b.json')
    a=p.parse_args()
    config=json.loads(Path(a.config).read_text(encoding='utf-8'))
    def model(messages,timeout,schema):
        return local_grammar_request(endpoint=a.model_url,schema=schema,
                                     n_predict=70,temperature=0.0)(messages,timeout)
    report=evaluate(config,model)
    Path(a.out).write_text(json.dumps(report,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2,sort_keys=True))
    if not report['summary']['different_private_experiment_changed_action']:
        print('NOT DEMONSTRATED: private experimental record changing selected action',
              file=sys.stderr)
        return 2
    return 0


if __name__=='__main__':
    sys.exit(main())
