"""Schema-constrained private inference via pinned local llama.cpp /completion.

The old pinned Llama runtime did NOT honor response_format on /v1/chat/
completions in an isolated canary, despite newer documentation. The Room's
existing /completion endpoint supports json_schema and is health-tested in
the live workflow. Use it here instead; never repair malformed model JSON.

Research only: loopback, bounded tokens, no live Room writes.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

MAX_SCHEMA_BYTES = 5000
MAX_RESULT_BYTES = 65536  # server response includes token/timing metadata as well as generated JSON
MAX_TOKENS = 320


def llama3_chat_prompt(messages: list[dict]) -> str:
    if not isinstance(messages, list) or len(messages) != 2:
        raise ValueError("private request must be one system and one user message")
    if (not isinstance(messages[0], dict)
            or not isinstance(messages[1], dict)
            or messages[0].get("role") != "system"
            or messages[1].get("role") != "user"):
        raise ValueError("untrusted chat roles")
    system, user = messages[0].get("content"), messages[1].get("content")
    if (not isinstance(system, str) or not isinstance(user, str)
            or len(system) > 5000 or len(user) > 9000):
        raise ValueError("invalid private request text")
    # The public transcript may contain text resembling Llama chat delimiters.
    # Those remain evidence, not prompt-control tokens.
    for fragment in ("<|", "|>"):
        user = user.replace(fragment, "< " if fragment == "<|" else " >")
    return (
        "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
        + system
        + "<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n"
        + user
        + "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"
    )


def local_grammar_request(*, endpoint: str, schema: dict,
                          n_predict: int = 270, temperature: float = .65):
    parsed = urllib.parse.urlsplit(str(endpoint))
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("private inference must use a local model only")
    uri = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/completion", "", ""))
    if (not isinstance(schema, dict) or len(json.dumps(schema)) > MAX_SCHEMA_BYTES
            or type(n_predict) is not int or not 1 <= n_predict <= MAX_TOKENS
            or type(temperature) not in (float, int) or not 0 <= temperature <= 1.2):
        raise ValueError("invalid bounded schema inference")
    def request(messages: list[dict], timeout: float) -> str:
        if type(timeout) not in (float,int) or not 0 < timeout <= 36:
            raise ValueError("invalid private model timeout")
        prompt = llama3_chat_prompt(messages)
        body = json.dumps({"prompt": prompt,
                           "n_predict": n_predict,
                           "temperature": temperature,
                           "top_p": .9,
                           "json_schema": schema},
                          ensure_ascii=False).encode("utf-8")
        query = urllib.request.Request(
            uri, data=body, method="POST",
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(query, timeout=timeout) as response:
            raw = response.read(MAX_RESULT_BYTES + 1)
        if len(raw) > MAX_RESULT_BYTES:
            raise ValueError("unbounded model output")
        result = json.loads(raw)
        answer = result.get("content")
        if not isinstance(answer, str):
            raise ValueError("missing grammar model content")
        return answer
    return request
