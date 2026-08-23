#!/usr/bin/env python3
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
MINUTES = ROOT / "minutes" / "minutes.md"
STATE = ROOT / "minutes" / "state.json"

SYSTEM = """You are the recording secretary for an ongoing meeting.
Write the next single line of the minutes.
Refer to earlier items by their number when it is relevant.
Keep it to one or two sentences in the register of official meeting minutes."""

SCHEMA = {
    "type": "object",
    "properties": {"entry": {"type": "string", "minLength": 40, "maxLength": 400}},
    "required": ["entry"],
    "additionalProperties": False,
}


def load_state():
    return json.loads(STATE.read_text(encoding="utf-8"))


def build_prompt(state):
    recent = state.get("recent", [])[-12:]
    lines = []
    for row in recent:
        if isinstance(row, dict):
            lines.append(f'{row["item"]}. {row["entry"]}')
        else:
            lines.append(str(row))
    return "RECENT_MINUTES\n" + "\n".join(lines) + f'\nNEXT_ITEM\n{state["item"]}'


def generate(state):
    api_key = os.environ["OPENAI_API_KEY"]
    model = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
    body = {
        "model": model,
        "input": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": build_prompt(state)},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "minutes_entry",
                "strict": True,
                "schema": SCHEMA,
            }
        },
    }
    req = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=90) as response:
        result = json.load(response)
    text = result.get("output_text")
    if not text:
        for output in result.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "output_text":
                    text = content.get("text")
                    break
            if text:
                break
    if not text:
        raise RuntimeError("Responses API returned no output_text")
    parsed = json.loads(text)
    entry = " ".join(parsed["entry"].split())
    if not 40 <= len(entry) <= 400:
        raise ValueError("entry violates required length")
    return entry


def main():
    state = load_state()
    item = int(state["item"])
    entry = generate(state)
    line = f"{item}. {entry}"

    MINUTES.parent.mkdir(parents=True, exist_ok=True)
    with MINUTES.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")

    recent = list(state.get("recent", []))
    recent.append({"item": item, "entry": entry})
    state = {"item": item + 1, "recent": recent[-12:]}
    STATE.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(line)


if __name__ == "__main__":
    main()
