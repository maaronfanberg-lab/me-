#!/usr/bin/env python3
"""Offline, real-model A/B of selected-floor source continuity.

Never publishes a Room beat. Uses exactly the Room's public input format and
production model-run code. Does not use prompt secrets or external inference.
Automated figures are diagnostics, not claims that dialogue is genuinely good.
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import room_private_model_autonomy as model
from room_conversational_floor import choose_next, is_directed
from room_conversation_evidence import analyze

NAMES = ("sarah", "mara", "owen", "jules")
STOP = {"the","and","that","this","with","from","have","your","what","when","where","which",
        "would","could","should","about","really","still","because","think","there","being","their",
        "they","them","you","are","for","but","our","has","was","can","not","just","then","into",
        "like","more","been","were","will","all","how","why","who","something","some","any"}


def words(value):
    return re.findall(r"[a-z]+", str(value or "").lower())


def diagnostic(source, response):
    a, b = words(source), words(response)
    salient = set(w for w in a if len(w) > 3 and w not in STOP)
    echoed = len(salient.intersection(b)) / max(1, len(salient))
    low = str(response or "").lower().strip()
    return {
        "salient_source_word_overlap": round(echoed, 3),
        "exact_echo": " ".join(a) == " ".join(b),
        "response_word_count": len(b),
        "placeholder_or_scaffold": bool(re.search(
            r"\b(?:new idea to be shared|implying an understanding|self_state|in this conversation|"
            r"what's next|what is the next point|conversation needs|try again)\b", low)),
    }


def simple_profile(config, entity):
    profile = dict((config.get("p") or {}).get(entity) or {})
    profile.setdefault("name", entity.capitalize())
    psyche = profile.get("psychology_v2") or {}
    return profile, {
        "who_i_am": str(psyche.get("core_identity") or f"I am {entity.capitalize()}."),
        "what_i_want": "Explore ideas and share what I actually notice.",
    }


def produce(history, speaker, profile, self_state, mode, counter):
    last = history[-1]
    reason = "open_floor_uptake" if mode == "retained" else ""
    os.environ["ROOM_CYCLE_KEY"] = f"shadow-comparison:{counter}:{speaker}"
    os.environ["ROOM_FLOOR_REASON"] = reason
    os.environ["ROOM_FLOOR_SOURCE_ID"] = str(last.get("id") or "")
    os.environ["ROOM_FLOOR_SPEAKER"] = speaker
    payload = {
        "entity": speaker, "profile": profile, "private_self_state": self_state,
        "event": last, "context": list(history[-3:]),
        "topic": {}, "keywords": [], "relationship": {},
        "partner": last.get("speaker"), "group_context": {},
    }
    try:
        result = model.run("expression", payload, timeout=80)
        if not isinstance(result, dict):
            return {"error":"model_output_quarantined","text":""}
        return {"text": str(result.get("utterance") or "").strip(),
                "move": result.get("move"), "target": result.get("target")}
    except Exception as exc:
        return {"error":type(exc).__name__,"text":""}


def sample_sources(conversation, count=12):
    picked = []
    for item in reversed(conversation[-160:]):
        if item.get("speaker") not in NAMES or not item.get("id"):
            continue
        content = str(item.get("text") or "").strip()
        if (not (12 <= len(words(content)) <= 78)
                or content.endswith("?")
                or any(is_directed(item, other) for other in NAMES)):
            continue
        if re.search(r"\bcategory\s+(?:classification|exploration)\s+trees\b", content, re.I):
            continue
        if any(len(set(words(content)) & set(words(x["text"]))) /
               max(1,len(set(words(content)) | set(words(x["text"])))) > 0.40 for x in picked):
            continue
        picked.append({"id":str(item["id"]), "speaker":item["speaker"],"text":content})
        if len(picked) >= count:
            break
    return list(reversed(picked))


def run():
    if not os.environ.get("ROOM_MODEL_URL"):
        raise RuntimeError("A real local model URL is required")
    os.environ["ROOM_CONVERSATIONAL_FLOOR"] = "1"
    os.environ.setdefault("ROOM_NODE_PROMPT", "Offline local conversation probe")
    feed=json.loads((ROOT/"room/feed.json").read_text(encoding="utf-8"))
    config=json.loads((ROOT/"room/config.json").read_text(encoding="utf-8"))
    sources=sample_sources(feed.get("conversation") or [])
    if len(sources)<8:
        raise RuntimeError(f"insufficient diverse public source turns: {len(sources)}")
    pair_tests=[]
    profiles={n:simple_profile(config,n) for n in NAMES}
    for i, source in enumerate(sources):
        other=[x for x in NAMES if x != source["speaker"]]
        speaker=other[i % len(other)]
        before=produce([source],speaker,*profiles[speaker],"baseline",i)
        after=produce([source],speaker,*profiles[speaker],"retained",i)
        pair_tests.append({
            "id":source["id"], "source_speaker":source["speaker"],"selected":speaker,
            "source":source["text"],
            "baseline":{**before,**diagnostic(source["text"],before.get("text"))},
            "retained":{**after,**diagnostic(source["text"],after.get("text"))},
        })
        print(f"MODEL PAIR {i+1}/{len(sources)} {source['speaker']}->{speaker} "
              f"baseline={len(before.get('text',''))} retained={len(after.get('text',''))}", flush=True)
    # Two independently generated multi-turn continuations, equal initial public
    # evidence and fixed sampler seeds, to expose repeated / disconnected runs.
    chain_source=sources[0]
    chains={}
    for mode in ("baseline","retained"):
        dialogue=[dict(chain_source)]
        for step in range(12):
            last=dialogue[-1]
            chosen=choose_next(dialogue,{"recurrent":{}},{"p":config.get("p") or {}},
                {"entities":{n:{"people":{}} for n in NAMES}})
            speaker=chosen["speaker"]
            out=produce(dialogue,speaker,*profiles[speaker],mode,100+step)
            if not out.get("text"):
                dialogue.append({"id":f"shadow-{mode}-{step}","speaker":speaker,
                                 "text":"[MODEL QUARANTINED OUTPUT]"})
                break
            dialogue.append({"id":f"shadow-{mode}-{step}","speaker":speaker,"text":out["text"]})
        chains[mode]={
            "turns":dialogue,
            "structural_diagnostics":analyze(dialogue)
        }
        print("MODEL CHAIN",mode,len(dialogue),flush=True)
    counters={}
    for mode in ("baseline","retained"):
        data=[x[mode] for x in pair_tests]
        valid=[x for x in data if x.get("text")]
        counters[mode]={
            "valid_outputs":len(valid),
            "mean_salient_source_word_overlap":
                round(sum(x["salient_source_word_overlap"] for x in valid)/len(valid),3) if valid else None,
            "exact_source_echoes":sum(x["exact_echo"] for x in valid),
            "placeholder_or_scaffold":sum(x["placeholder_or_scaffold"] for x in valid),
            "short_outputs_1to3_words":sum(x["response_word_count"]<=3 for x in valid),
        }
    result={
        "purpose":"shadow A/B; structural indicators plus text for human qualitative scoring",
        "model":os.environ.get("ROOM_MODEL_NAME","production-llama3.2-1b-local"),
        "source_cycle":(feed.get("state") or {}).get("cycle"),
        "sample_count":len(pair_tests),
        "counters":counters,
        "pairs":pair_tests,
        "chains":chains,
        "interpretation":"No conclusions about genuine conversation from token overlap; inspect paired replies and 12-turn continuations manually. Same local model, seeds, public input data; no publication.",
    }
    output=ROOT/"docs/research/room-floor-shadow-20261028.json"
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("SHADOW SUMMARY",json.dumps(counters),flush=True)


if __name__=="__main__":
    run()
