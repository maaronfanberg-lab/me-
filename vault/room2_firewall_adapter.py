from __future__ import annotations
import copy
import room2_runtime_firewall


def validate(feed, report, history, speech, sanitizer, heartbeat):
    r=copy.deepcopy(report) if isinstance(report,dict) else report
    if isinstance(r,dict):
        if str(r.get('version','')).startswith('room-2-shadow-v'):
            r['version']='room-vault-shadow-v'+str(r.get('version')).rsplit('v',1)[-1]
        summaries=r.get('semantic_summaries') if isinstance(r.get('semantic_summaries'),dict) else {}
        entities=r.get('entities') if isinstance(r.get('entities'),dict) else {}
        for name,entry in entities.items():
            if isinstance(entry,dict):
                if 'regime_change' not in entry and 'regime_l1_change' in entry:
                    entry['regime_change']=entry.get('regime_l1_change')
                if 'semantic_summary' not in entry:
                    entry['semantic_summary']=summaries.get(name,'')
    return room2_runtime_firewall.validate(feed,r,history,speech,sanitizer,heartbeat)
