#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, 'scripts')
import room_engine_v5 as room


def main():
    guidance = room._expression_retry_guidance
    assert 'Do not reuse any complete sentence' in guidance('same_beat_sentence_copy')
    assert 'Change the underlying contribution' in guidance('same_beat_semantic_coverage')
    assert 'Change the underlying contribution' in guidance('same_beat_restatement_sentence')
    assert 'without recapping it' in guidance('duplicate_context')
    assert 'complete valid JSON object' in guidance('Unterminated string starting at: line 1 column 47')

    captured = []
    originals = {
        'compact': room._private_model._compact_payload,
        'request': room._private_model._request,
        'extract': room._private_model._extract_json,
        'validate': room._private_model._validate,
        'sanitize': room._private_model._sanitize_expression,
        'quality': room._expression_quality.quality_issue,
    }
    old_prompt = os.environ.get('ROOM_NODE_PROMPT')
    old_url = os.environ.get('ROOM_MODEL_URL')
    try:
        os.environ['ROOM_NODE_PROMPT'] = 'Return JSON.'
        os.environ['ROOM_MODEL_URL'] = 'http://unused'
        room._private_model._compact_payload = lambda role, payload: {'entity': payload.get('entity', 'sarah')}

        def fake_request(model_url, prompt, role, temperature, timeout, self_entity=None, attempt=0):
            captured.append(prompt)
            return '{"utterance":"fresh point"}'

        room._private_model._request = fake_request
        room._private_model._extract_json = lambda raw: {'utterance': 'fresh point'}
        room._private_model._validate = lambda role, obj: obj
        room._private_model._sanitize_expression = lambda obj, self_entity=None: obj
        outcomes = iter(['same_beat_sentence_copy', None])
        room._expression_quality.quality_issue = lambda expression, payload: next(outcomes)

        result = room._private_run('expression', {'entity': 'sarah'}, timeout=1)
        assert result == {'utterance': 'fresh point'}, result
        assert len(captured) == 2, captured
        assert 'RETRY CONTROL:' not in captured[0], captured[0]
        assert 'Do not reuse any complete sentence' in captured[1], captured[1]
        assert 'same_beat_sentence_copy' not in captured[1], 'validator implementation detail leaked into prompt'
        print('PASS: rejected expression receives reason-aware retry control')
        print('PASS: retry guidance remains control-only and validator stays authoritative')
    finally:
        room._private_model._compact_payload = originals['compact']
        room._private_model._request = originals['request']
        room._private_model._extract_json = originals['extract']
        room._private_model._validate = originals['validate']
        room._private_model._sanitize_expression = originals['sanitize']
        room._expression_quality.quality_issue = originals['quality']
        if old_prompt is None:
            os.environ.pop('ROOM_NODE_PROMPT', None)
        else:
            os.environ['ROOM_NODE_PROMPT'] = old_prompt
        if old_url is None:
            os.environ.pop('ROOM_MODEL_URL', None)
        else:
            os.environ['ROOM_MODEL_URL'] = old_url


if __name__ == '__main__':
    main()
