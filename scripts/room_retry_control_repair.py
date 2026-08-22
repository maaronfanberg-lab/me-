#!/usr/bin/env python3
from pathlib import Path

path = Path('scripts/room_expression_quality_core.py')
text = path.read_text()
old = '''    def _quality_request(model_url, prompt, role, temperature, timeout, self_entity=None, attempt=0):
        return _original_request(
            model_url,
            _strip_retry_prose(prompt),
            role,
            temperature,
            timeout,
            self_entity,
            attempt,
        )
'''
new = '''    def _quality_request(model_url, prompt, role, temperature, timeout, self_entity=None, attempt=0):
        # Expression transport separates control from conversational situation.
        # Keep retry guidance in the control channel so a rejected echo receives
        # a genuinely different instruction; never place it in situation data.
        request_prompt = str(prompt or "")
        if role != "expression":
            request_prompt = _strip_retry_prose(request_prompt)
        return _original_request(
            model_url,
            request_prompt,
            role,
            temperature,
            timeout,
            self_entity,
            attempt,
        )
'''
if new in text:
    print('PASS: retry-control repair already present')
elif text.count(old) == 1:
    path.write_text(text.replace(old, new, 1))
    print('PASS: retry-control repair applied')
else:
    raise SystemExit('FAIL: live retry-control boundary does not match guarded source')
