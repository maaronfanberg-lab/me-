from __future__ import annotations
import copy
import room2_runtime_firewall


def validate(feed, report, history, speech, sanitizer, heartbeat):
    r=copy.deepcopy(report) if isinstance(report,dict) else report
    if isinstance(r,dict):
        summaries=r.get('semantic_summaries') if isinstance(r.get('semantic_summaries'),dict) else {}
        entities=r.get('entities') if isinstance(r.get('entities'),dict) else {}
        for name,entry in entities.items():
            if isinstance(entry,dict):
                if 'regime_change' not in entry and 'regime_l1_change' in entry:
                    entry['regime_change']=entry.get('regime_l1_change')
                if 'semantic_summary' not in entry:
                    entry['semantic_summary']=summaries.get(name,'')
    result=room2_runtime_firewall.validate(feed,r,history,speech,sanitizer,heartbeat)
    failures=list(result.get('failures') or [])
    passed=int(result.get('passed') or 0)

    feed_cycle=((feed.get('state') or {}).get('cycle') if isinstance(feed,dict) and isinstance(feed.get('state'),dict) else None)
    report_cycle=(r.get('source_cycle') if isinstance(r,dict) else None)
    heartbeat_cycle=(heartbeat.get('source_cycle') if isinstance(heartbeat,dict) else None)

    cross_checks={
        '101_feed_report_cycle_match': isinstance(feed_cycle,int) and isinstance(report_cycle,int) and feed_cycle==report_cycle,
        '102_heartbeat_report_cycle_match': isinstance(heartbeat_cycle,int) and isinstance(report_cycle,int) and heartbeat_cycle==report_cycle,
    }
    if isinstance(speech,dict) and speech.get('spoke') is True:
        entry=speech.get('entry') if isinstance(speech.get('entry'),dict) else {}
        cross_checks['103_speech_report_cycle_match']=isinstance(entry.get('source_cycle'),int) and isinstance(report_cycle,int) and entry.get('source_cycle')==report_cycle
    else:
        cross_checks['103_speech_report_cycle_match']=True

    for name,ok in cross_checks.items():
        if ok:
            passed+=1
        else:
            failures.append(name)
    return {'ok':not failures,'passed':passed,'failed':len(failures),'failures':failures}
