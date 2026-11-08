#!/usr/bin/env python3
"""Real pinned 3B comparison: one explicit instrument choice, no fake goals.

All actions are simulated and owner-originated. The exact same behavioral gate
used for the eight-field baseline remains in force. No live Room modification.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from room_endogenous_activity_3b_canary import experiment, SPEECH_SCHEMA
from room_endogenous_activity_compact import adapter, SCHEMA
from room_endogenous_schema_transport import local_grammar_request


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model-url',required=True)
    p.add_argument('--config',default='room/config.json')
    p.add_argument('--out',default='room-activity-compact-real3b.json')
    p.add_argument('--beats',type=int,default=4)
    args=p.parse_args()
    config=json.loads(Path(args.config).read_text(encoding='utf-8'))
    one_choice=local_grammar_request(endpoint=args.model_url,schema=SCHEMA,
                                      n_predict=62,temperature=.44)
    tool=adapter(one_choice)
    speech=local_grammar_request(endpoint=args.model_url,schema=SPEECH_SCHEMA,
                                  n_predict=160,temperature=.42)
    report=experiment(config,tool,speech,beats=args.beats)
    report['action_interface']='one_explicit_self_selected_instrument'
    report['baseline']='eight_field_model_choice'
    report['summary']['compact_interface_real_model_passed']=bool(
        report['summary']['computational_agency_observed'])
    Path(args.out).write_text(json.dumps(report,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,sort_keys=True,indent=2))
    if not report['summary']['computational_agency_observed']:
        print('FAILED: own-model computational actions below the unchanged gate',file=sys.stderr)
        return 2
    return 0


if __name__=='__main__':
    sys.exit(main())
