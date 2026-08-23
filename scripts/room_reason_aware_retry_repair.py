#!/usr/bin/env python3
from pathlib import Path

path = Path('scripts/room_engine_v5.py')
text = path.read_text()

helper_anchor = '''def _private_run(role: str, payload: dict, timeout: int = 30):
'''
helper = '''def _expression_retry_guidance(reason):
    """Turn a private expression rejection into a narrow retry control instruction."""
    reason = str(reason or "").lower()
    if "same_beat_sentence_copy" in reason:
        return (
            "\\nRETRY CONTROL: The previous draft copied language from this beat. "
            "Do not reuse any complete sentence, clause, or distinctive phrasing from earlier same-beat replies. "
            "Make a genuinely new conversational contribution and phrase it from scratch. "
            "Keep the reply concise, grammatically complete, and valid JSON."
        )
    if "same_beat_semantic_coverage" in reason or "same_beat_restatement_sentence" in reason:
        return (
            "\\nRETRY CONTROL: The previous draft restated a point already made in this beat. "
            "Change the underlying contribution, not merely the wording: add a distinct consequence, example, "
            "question, disagreement, or concrete implication that advances the conversation. "
            "Keep the reply concise, grammatically complete, and valid JSON."
        )
    if "duplicate_context" in reason:
        return (
            "\\nRETRY CONTROL: The previous draft repeated or summarized existing context. "
            "React to the newest turn without recapping it, and contribute one new concrete point. "
            "Keep the reply concise, grammatically complete, and valid JSON."
        )
    if "unterminated string" in reason or "json" in reason or "delimiter" in reason:
        return (
            "\\nRETRY CONTROL: The previous response was structurally malformed or truncated. "
            "Use a shorter utterance and return one complete valid JSON object with no trailing prose."
        )
    return (
        "\\nRETRY CONTROL: The previous draft was rejected. Use a different idea and wording while staying with "
        "the same conversation. Keep the reply concise, grammatically complete, and valid JSON."
    )


def _private_run(role: str, payload: dict, timeout: int = 30):
'''

retry_old = '''        retry = ""
        if attempt:
            retry = "\\nUse a different idea and wording while staying with the same conversation. Keep the reply concise and grammatically complete."
'''
retry_new = '''        retry = ""
        if attempt:
            retry = _expression_retry_guidance(last_reason) if role == "expression" else (
                "\\nUse a different idea and wording while staying with the same conversation. "
                "Keep the reply concise and grammatically complete."
            )
'''

if helper in text and retry_new in text:
    print('PASS: reason-aware expression retry already present')
elif text.count(helper_anchor) == 1 and text.count(retry_old) == 1:
    text = text.replace(helper_anchor, helper, 1)
    text = text.replace(retry_old, retry_new, 1)
    path.write_text(text)
    print('PASS: reason-aware expression retry applied')
else:
    raise SystemExit('FAIL: live expression retry boundary does not match guarded source')
