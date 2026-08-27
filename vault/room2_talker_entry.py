from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import history_sanitizer
import room2_firewall_adapter
import room2_guardrails
import vault_talker

_original_has_ngram_echo = vault_talker._has_ngram_echo
_original_quality_check = vault_talker.quality_check


def _balanced_echo_guard(text, sources, n=5):
    effective_n = 6 if n == 5 else (8 if n >= 7 else n)
    return _original_has_ngram_echo(text, sources, n=effective_n)


def _hardened_quality_check(text, entity, recent, live_context, archive):
    accepted, reason = _original_quality_check(text, entity, recent, live_context, archive)
    if not accepted: return accepted, reason
    grounding = list(live_context) + list(recent[-6:])
    if room2_guardrails.has_unsupported_accusation(text): return False, "unsupported_accusation"
    if room2_guardrails.excessive_second_person(text): return False, "second_person_excess"
    if room2_guardrails.malformed_identity_claim(text): return False, "identity_claim"
    if room2_guardrails.weak_grounding(text, grounding): return False, "weak_grounding"
    if room2_guardrails.semantic_repeat(text, recent): return False, "semantic_repeat"
    if room2_guardrails.repetitive_opening(text, recent): return False, "repetitive_opening"
    return True, "ok"


def sanitize_history_argument(argv: list[str]) -> dict:
    if len(argv) < 4: return {"removed": 0, "kept": 0}
    path=Path(argv[3]); value=vault_talker._load(path, [])
    clean,stats=history_sanitizer.sanitize_history(value)
    vault_talker._atomic_json(path, clean)
    return stats


def _arg_value(flag: str) -> str | None:
    try: return sys.argv[sys.argv.index(flag)+1]
    except Exception: return None


def _postflight() -> None:
    feed_path=Path(sys.argv[1]); report_path=Path(sys.argv[2]); history_path=Path(sys.argv[3])
    result_arg=_arg_value('--result')
    if not result_arg: raise SystemExit('missing --result')
    result_path=Path(result_arg)
    clean,stats=history_sanitizer.sanitize_history(vault_talker._load(history_path, []))
    vault_talker._atomic_json(history_path, clean)
    sanitizer_path=history_path.parent/'sanitizer-report.json'
    vault_talker._atomic_json(sanitizer_path, stats)
    report=vault_talker._load(report_path,{})
    heartbeat={
        'version':'room-2-heartbeat-v3','at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'run_id':os.environ.get('ROOM2_RUN_ID'),'source_cycle':report.get('source_cycle'),
        'health':(report.get('health') or {}).get('status') if isinstance(report.get('health'),dict) else None,
        'conversation_size':len(clean),'llm_active':True,'feedback_loop':True,
        'sanitizer_removed':int(stats.get('removed') or 0),
    }
    heartbeat_path=history_path.parent/'heartbeat.json'; vault_talker._atomic_json(heartbeat_path, heartbeat)
    firewall=room2_firewall_adapter.validate(vault_talker._load(feed_path,{}),report,clean,vault_talker._load(result_path,{}),stats,heartbeat)
    vault_talker._atomic_json(history_path.parent/'firewall-report.json', firewall)
    if not firewall.get('ok'):
        raise SystemExit('ROOM 2 runtime firewall: '+','.join(firewall.get('failures',[])[:20]))


def main() -> None:
    stats=sanitize_history_argument(sys.argv)
    if stats.get('removed'): print(f"ROOM 2 quarantined {stats['removed']} persisted utterance(s).")
    vault_talker._has_ngram_echo=_balanced_echo_guard
    vault_talker.quality_check=_hardened_quality_check
    vault_talker.main(); _postflight()


if __name__ == '__main__': main()
