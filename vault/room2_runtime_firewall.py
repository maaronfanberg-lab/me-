from __future__ import annotations

import json, math, re, sys
from datetime import datetime, timezone
from pathlib import Path

ENTITIES = {"sarah", "mara", "owen", "jules"}
REGIMES = {"settled", "exploratory", "social", "transition"}
VALID_SPEECH_REASONS = {"latent_candidate", "latent_candidate_fair", "bounded_idle_turn", "bounded_idle_fair", "quality_rejected", "generation_failed", "missing_cycle", "missing_context", "idle_cooldown", "history_clock_future", "no_candidates", "talker_process_failed"}


def _finite(x):
    try: return math.isfinite(float(x))
    except Exception: return False

def _time(x):
    try:
        d=datetime.fromisoformat(str(x).replace('Z','+00:00'))
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception: return None

def _load(path):
    return json.loads(Path(path).read_text())

def validate(feed, report, history, speech, sanitizer, heartbeat):
    failures=[]; passed=[]
    def ck(name, cond): (passed if cond else failures).append(name)
    now=datetime.now(timezone.utc)

    # Source feed 1-15
    ck('01_feed_dict', isinstance(feed,dict))
    conv=feed.get('conversation') if isinstance(feed,dict) else None
    ck('02_feed_conversation_list', isinstance(conv,list))
    ck('03_feed_conversation_bound', isinstance(conv,list) and len(conv)<=2000)
    ck('04_feed_generated_present', bool(feed.get('generated_at')))
    fg=_time(feed.get('generated_at'))
    ck('05_feed_generated_parseable', fg is not None)
    ck('06_feed_generated_not_far_future', fg is not None and (fg-now).total_seconds()<600)
    state=feed.get('state') if isinstance(feed.get('state'),dict) else {}
    ck('07_feed_state_dict', isinstance(feed.get('state'),dict))
    cycle=state.get('cycle')
    ck('08_feed_cycle_intish', isinstance(cycle,int) and cycle>=0)
    ck('09_feed_cycle_bounded', isinstance(cycle,int) and cycle<10**9)
    brain=feed.get('brain') if isinstance(feed.get('brain'),dict) else {}
    ck('10_feed_brain_dict', isinstance(feed.get('brain'),dict))
    ck('11_feed_no_runtime_write_flag', feed.get('production_write_enabled') is not True)
    ck('12_feed_items_dicts', isinstance(conv,list) and all(isinstance(x,dict) for x in conv))
    ck('13_feed_text_bounded', isinstance(conv,list) and all(len(str(x.get('text','')))<=5000 for x in conv if isinstance(x,dict)))
    ck('14_feed_speaker_bounded', isinstance(conv,list) and all(len(str(x.get('speaker','')))<=100 for x in conv if isinstance(x,dict)))
    ck('15_feed_ids_bounded', isinstance(conv,list) and all(len(str(x.get('id','')))<=300 for x in conv if isinstance(x,dict)))

    # Report 16-40
    ck('16_report_dict', isinstance(report,dict))
    ck('17_report_version', str(report.get('version','')).startswith('room-vault-shadow-v'))
    ck('18_report_prod_write_false', report.get('production_write_enabled') is False)
    ck('19_report_shadow_speech_false', report.get('speech_requested') is False)
    ck('20_report_entities_dict', isinstance(report.get('entities'),dict))
    ents=report.get('entities') if isinstance(report.get('entities'),dict) else {}
    ck('21_report_exact_entities', set(ents)==ENTITIES)
    ck('22_report_candidates_dict', isinstance(report.get('candidates'),dict))
    cands=report.get('candidates') if isinstance(report.get('candidates'),dict) else {}
    ck('23_report_candidate_entities', set(cands).issubset(ENTITIES))
    ck('24_report_max_one_request', sum(1 for x in cands.values() if isinstance(x,dict) and x.get('would_request_speech') is True)<=1)
    ck('25_report_source_cycle_nonnegative', isinstance(report.get('source_cycle'),int) and report.get('source_cycle')>=0)
    health=report.get('health') if isinstance(report.get('health'),dict) else {}
    ck('26_report_health_dict', isinstance(report.get('health'),dict))
    ck('27_report_health_known', health.get('status') in {'ok','degraded'})
    ck('28_report_processed_nonnegative', isinstance(report.get('processed_messages'),int) and report.get('processed_messages')>=0)
    ck('29_report_processed_bounded', isinstance(report.get('processed_messages'),int) and report.get('processed_messages')<=2000)
    ck('30_report_llm_shadow_false', report.get('llm_enabled') is False)
    for e in ENTITIES:
        x=ents.get(e,{}) if isinstance(ents.get(e),dict) else {}
        probs=x.get('regime_probabilities')
        ck(f'31_{e}_dict', isinstance(ents.get(e),dict))
        ck(f'32_{e}_regime_known', x.get('dominant_regime') in REGIMES)
        ck(f'33_{e}_probs_len4', isinstance(probs,list) and len(probs)==4)
        ck(f'34_{e}_probs_finite', isinstance(probs,list) and len(probs)==4 and all(_finite(v) for v in probs))
        ck(f'35_{e}_probs_nonnegative', isinstance(probs,list) and len(probs)==4 and all(float(v)>=0 for v in probs if _finite(v)))
        ck(f'36_{e}_probs_sum', isinstance(probs,list) and len(probs)==4 and abs(sum(float(v) for v in probs)-1)<1e-5)
        ck(f'37_{e}_entropy', _finite(x.get('entropy')) and 0<=float(x.get('entropy'))<=1.000001)
        ck(f'38_{e}_change', _finite(x.get('regime_change')) and 0<=float(x.get('regime_change'))<=2)
        ck(f'39_{e}_observables', isinstance(x.get('observables'),list) and len(x.get('observables'))==10 and all(_finite(v) for v in x.get('observables')))
        ck(f'40_{e}_summary_bounded', len(str(x.get('semantic_summary','')))<=600)

    # History 41-65
    ck('41_history_list', isinstance(history,list))
    ck('42_history_bound', isinstance(history,list) and len(history)<=120)
    ck('43_history_items_dict', isinstance(history,list) and all(isinstance(x,dict) for x in history))
    ck('44_history_speakers', isinstance(history,list) and all(x.get('speaker') in ENTITIES for x in history if isinstance(x,dict)))
    ids=[str(x.get('id') or '') for x in history if isinstance(x,dict)] if isinstance(history,list) else []
    ck('45_history_ids_present', bool(ids) and all(ids) if history else True)
    ck('46_history_ids_unique', len(ids)==len(set(ids)))
    ck('47_history_ids_bound', all(len(x)<=160 for x in ids))
    texts=[str(x.get('text') or '') for x in history if isinstance(x,dict)] if isinstance(history,list) else []
    ck('48_history_text_present', all(t.strip() for t in texts))
    ck('49_history_text_bound', all(12<=len(t)<=360 for t in texts))
    ck('50_history_terminal_punct', all(t[-1:] in '.?!' for t in texts))
    ck('51_history_no_control', all(not re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]',t) for t in texts))
    ck('52_history_no_machine_meta', all(not re.search(r'inner_state|regime_entropy|candidate_budget|would_request_speech',t,re.I) for t in texts))
    ck('53_history_no_urls', all(not re.search(r'https?://|www\.',t,re.I) for t in texts))
    ck('54_history_no_empty_identity', all(not re.match(r'^\s*(sarah|mara|owen|jules)\s*$',t,re.I) for t in texts))
    times=[_time(x.get('at')) for x in history if isinstance(x,dict)] if isinstance(history,list) else []
    ck('55_history_times_parse', all(t is not None for t in times))
    ck('56_history_times_not_future', all(t is not None and (t-now).total_seconds()<600 for t in times))
    ck('57_history_chronological', all(times[i]<=times[i+1] for i in range(len(times)-1) if times[i] and times[i+1]))
    ck('58_history_cycles_valid', all(x.get('source_cycle') is None or (isinstance(x.get('source_cycle'),int) and 0<=x.get('source_cycle')<10**9) for x in history if isinstance(x,dict)))
    ck('59_history_reasons_bound', all(len(str(x.get('reason','')))<=80 for x in history if isinstance(x,dict)))
    ck('60_history_no_exact_text_dupes', len({re.sub(r'\W+',' ',t.lower()).strip() for t in texts})==len(texts))
    ck('61_history_words_min', all(len(re.findall(r"[a-z0-9']+",t.lower()))>=7 for t in texts))
    ck('62_history_words_max', all(len(re.findall(r"[a-z0-9']+",t.lower()))<=48 for t in texts))
    ck('63_history_no_nul', all('\x00' not in t for t in texts))
    ck('64_history_known_fields', all(set(x).issubset({'id','speaker','text','at','source_cycle','reason'}) for x in history if isinstance(x,dict)))
    ck('65_history_recent_reason_known', all((x.get('reason') in VALID_SPEECH_REASONS or x.get('reason') in {'latent_candidate','latent_candidate_fair','bounded_idle_turn','bounded_idle_fair'}) for x in history if isinstance(x,dict)))

    # Speech result 66-80
    ck('66_speech_dict', isinstance(speech,dict))
    ck('67_speech_spoke_bool', isinstance(speech.get('spoke'),bool))
    ck('68_speech_reason_present', isinstance(speech.get('reason'),str) and bool(speech.get('reason')))
    ck('69_speech_reason_bound', len(str(speech.get('reason','')))<=100)
    ck('70_speech_entity_valid', speech.get('entity') is None or speech.get('entity') in ENTITIES)
    ck('71_speech_attempts_nonnegative', isinstance(speech.get('attempts',0),int) and speech.get('attempts',0)>=0)
    ck('72_speech_attempts_bound', isinstance(speech.get('attempts',0),int) and speech.get('attempts',0)<=10)
    rej=speech.get('rejections',{})
    ck('73_speech_rejections_dict', isinstance(rej,dict))
    ck('74_speech_rejection_keys_bound', isinstance(rej,dict) and all(len(str(k))<=100 for k in rej))
    ck('75_speech_rejection_counts', isinstance(rej,dict) and all(isinstance(v,int) and 0<=v<=10 for v in rej.values()))
    ck('76_speech_entry_if_spoke', (not speech.get('spoke')) or isinstance(speech.get('entry'),dict))
    entry=speech.get('entry') if isinstance(speech.get('entry'),dict) else {}
    ck('77_speech_entry_speaker', (not speech.get('spoke')) or entry.get('speaker') in ENTITIES)
    ck('78_speech_entry_text', (not speech.get('spoke')) or (isinstance(entry.get('text'),str) and 12<=len(entry.get('text'))<=360))
    ck('79_speech_entry_id', (not speech.get('spoke')) or (isinstance(entry.get('id'),str) and bool(entry.get('id'))))
    ck('80_speech_entry_in_history', (not speech.get('spoke')) or any(x.get('id')==entry.get('id') for x in history if isinstance(x,dict)))

    # Sanitizer 81-88
    ck('81_sanitizer_dict', isinstance(sanitizer,dict))
    ck('82_sanitizer_removed_nonnegative', isinstance(sanitizer.get('removed',0),int) and sanitizer.get('removed',0)>=0)
    ck('83_sanitizer_kept_nonnegative', isinstance(sanitizer.get('kept',0),int) and sanitizer.get('kept',0)>=0)
    ck('84_sanitizer_kept_matches_history', sanitizer.get('kept')==len(history))
    ck('85_sanitizer_removed_bounded', sanitizer.get('removed',0)<=240)
    ck('86_sanitizer_recovered_nonnegative', isinstance(sanitizer.get('recovered_ids',0),int) and sanitizer.get('recovered_ids',0)>=0)
    ck('87_sanitizer_duplicate_counts', all(isinstance(sanitizer.get(k,0),int) and sanitizer.get(k,0)>=0 for k in ('duplicate_ids','duplicate_text')))
    ck('88_sanitizer_bad_counts', all(isinstance(sanitizer.get(k,0),int) and sanitizer.get(k,0)>=0 for k in ('bad_timestamps','bad_cycles','bad_reasons')))

    # Heartbeat/isolation 89-100
    ck('89_heartbeat_dict', isinstance(heartbeat,dict))
    ck('90_heartbeat_version', heartbeat.get('version')=='room-2-heartbeat-v3')
    ht=_time(heartbeat.get('at'))
    ck('91_heartbeat_time_parse', ht is not None)
    ck('92_heartbeat_freshish', ht is not None and -30<=(now-ht).total_seconds()<=900)
    ck('93_heartbeat_run_id', str(heartbeat.get('run_id') or '').isdigit())
    ck('94_heartbeat_cycle', isinstance(heartbeat.get('source_cycle'),int) and heartbeat.get('source_cycle')>=0)
    ck('95_heartbeat_health', heartbeat.get('health') in {'ok','degraded'})
    ck('96_heartbeat_conversation_size', heartbeat.get('conversation_size')==len(history))
    ck('97_heartbeat_llm_true', heartbeat.get('llm_active') is True)
    ck('98_heartbeat_feedback_true', heartbeat.get('feedback_loop') is True)
    ck('99_heartbeat_sanitizer_count', isinstance(heartbeat.get('sanitizer_removed'),int) and heartbeat.get('sanitizer_removed')>=0)
    ck('100_isolation_tripwire', report.get('production_write_enabled') is False and report.get('speech_requested') is False and feed.get('origin')!='room2-production')

    return {'ok':not failures,'passed':len(passed),'failed':len(failures),'failures':failures}


def main():
    if len(sys.argv)!=7:
        raise SystemExit('usage: firewall feed report history speech sanitizer heartbeat')
    vals=[_load(p) for p in sys.argv[1:]]
    result=validate(*vals)
    print(json.dumps(result,indent=2))
    if not result['ok']: raise SystemExit(2)

if __name__=='__main__': main()
