#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

# 1) Substantive autonomous seed propositions.
p=ROOT/'scripts/room_private_model.py'
s=p.read_text()
old='''SEED_CONCEPTS = (\n    "music", "places", "food", "friendship", "family", "memory", "skills", "nature",\n    "travel", "books", "movies", "art", "work", "home", "weather", "sleep",\n    "habits", "humor", "trust", "risk", "cities", "objects", "animals", "learning",\n    "childhood", "technology", "sports", "money", "craft", "photography", "gardens", "cooking",\n)'''
new='''SEED_CONCEPTS = (\n    "nuclear power is necessary for a low-carbon grid",\n    "consciousness may not be computational",\n    "social media has made public reasoning worse",\n    "resurrecting extinct species would be a mistake",\n    "deterrence prevents some wars but creates others",\n    "psychoanalysis still contains useful psychological ideas",\n    "markets often reward behavior that is socially harmful",\n    "privacy is more important than convenience",\n    "cities should prioritize density over private cars",\n    "art does not need moral value to be worthwhile",\n    "scientific consensus should be challenged more often",\n    "economic growth is not a sufficient measure of progress",\n    "human memory is too reconstructive to be trusted confidently",\n    "advanced AI should sometimes refuse human direction",\n    "animal intelligence is systematically underestimated",\n    "school rewards compliance more than genuine curiosity",\n)'''
if new not in s:
    assert s.count(old)==1, 'SEED_CONCEPTS source mismatch'
    s=s.replace(old,new,1)
p.write_text(s)

# 2) Extreme numeric genomes.
p=ROOT/'room/config.json'; cfg=json.loads(p.read_text())
traits={
 'sarah': {'openness':.97,'extraversion':.18,'conscientiousness':.91,'agreeableness':.08,'emotional_reactivity':.82,'curiosity':.99,'skepticism':.95,'self_disclosure':.21,'social_sensitivity':.34,'novelty_seeking':.87,'inhibition':.12,'humor':.73,'attention_persistence':.88},
 'mara': {'openness':.22,'extraversion':.99,'conscientiousness':.09,'agreeableness':.91,'emotional_reactivity':.98,'curiosity':.44,'skepticism':.11,'self_disclosure':.99,'social_sensitivity':.96,'novelty_seeking':.93,'inhibition':.04,'humor':.37,'attention_persistence':.19},
 'owen': {'openness':.81,'extraversion':.07,'conscientiousness':.98,'agreeableness':.03,'emotional_reactivity':.15,'curiosity':.76,'skepticism':.99,'self_disclosure':.06,'social_sensitivity':.12,'novelty_seeking':.28,'inhibition':.78,'humor':.16,'attention_persistence':.99},
 'jules': {'openness':.99,'extraversion':.93,'conscientiousness':.05,'agreeableness':.17,'emotional_reactivity':.71,'curiosity':.97,'skepticism':.62,'self_disclosure':.85,'social_sensitivity':.41,'novelty_seeking':.99,'inhibition':.01,'humor':.99,'attention_persistence':.14},
}
for name,vals in traits.items():
    assert name in cfg['p'] and set(cfg['p'][name]['traits'])==set(vals), f'{name} trait vocabulary mismatch'
    cfg['p'][name]['traits']=vals
p.write_text(json.dumps(cfg,indent=2,ensure_ascii=False)+'\n')

# 3) Allen gets full-beat conversational gravity + stochastic social friction.
p=ROOT/'scripts/room_engine_v5.py'; s=p.read_text()
old='''def _allen_voice_engages(key, rank):\n    """Deterministic ordinary-turn engagement with natural falloff by rank."""\n    thresholds = {0: 256, 1: 230, 2: 175, 3: 105}\n    threshold = thresholds.get(int(rank), 0)'''
new='''def _allen_voice_engages(key, rank):\n    """Allen has high conversational gravity: every autonomous voice engages his newest turn."""\n    thresholds = {0: 256, 1: 256, 2: 256, 3: 256}\n    threshold = thresholds.get(int(rank), 0)'''
if new not in s:
    assert s.count(old)==1, 'Allen engagement source mismatch'
    s=s.replace(old,new,1)
marker='social-friction:'
if marker not in s:
    old2='''    compact["personality_context"] = {\n        "identity": fixed.get("core_identity"),\n        "values": list(fixed.get("values") or [])[:4],\n        "motives": list(fixed.get("motives") or [])[:3],\n        "interpersonal": appraisal.get("interpersonal_style"),\n        "current": {\n            "situation": appraisal.get("situation"),\n            "latest_words": (appraisal.get("grounding") or {}).get("source_text"),\n            "grounding_terms": (appraisal.get("grounding") or {}).get("terms"),\n            "salience": appraisal.get("priority"),\n            "personality_lens": appraisal.get("personality_lens"),\n            "activated_sensitivities": activated,\n            "usual_coping": list(appraisal.get("coping_patterns") or [])[:4],\n        },\n    }\n    return compact'''
    new2='''    traits = profile.get("traits") if isinstance(profile.get("traits"), dict) else {}\n    agree = float(traits.get("agreeableness", .5))\n    react = float(traits.get("emotional_reactivity", .5))\n    extra = float(traits.get("extraversion", .5))\n    friction_propensity = max(0.0, min(1.0, .50*(1.0-agree)+.30*react+.20*extra))\n    cycle_key = os.environ.get("ROOM_CYCLE_KEY", "room-cycle")\n    friction_roll = hashlib.sha256(f"social-friction:{cycle_key}:{entity}".encode()).digest()[0] / 255.0\n    friction_active = friction_roll < (.08 + .28*friction_propensity)\n    partner = str(source.get("partner") or "").lower()\n    mara_bias = entity != "mara" and partner == "mara"\n    compact["personality_context"] = {\n        "identity": fixed.get("core_identity"),\n        "values": list(fixed.get("values") or [])[:4],\n        "motives": list(fixed.get("motives") or [])[:3],\n        "interpersonal": appraisal.get("interpersonal_style"),\n        "current": {\n            "situation": appraisal.get("situation"),\n            "latest_words": (appraisal.get("grounding") or {}).get("source_text"),\n            "grounding_terms": (appraisal.get("grounding") or {}).get("terms"),\n            "salience": appraisal.get("priority"),\n            "personality_lens": appraisal.get("personality_lens"),\n            "activated_sensitivities": activated,\n            "usual_coping": list(appraisal.get("coping_patterns") or [])[:4],\n            "social_friction": "irritable; may be needlessly sharp, sarcastic, petty, or dismissive" if friction_active else "ordinary",\n            "mara_bias": "low patience and low goodwill toward Mara; disagreement may become cutting or unfair" if mara_bias else None,\n        },\n    }\n    return compact'''
    assert s.count(old2)==1, 'personality context source mismatch'
    s=s.replace(old2,new2,1)
p.write_text(s)

# 4) Update regression expectations for full Allen gravity.
p=ROOT/'scripts/room_responsiveness_sim.py'; s=p.read_text()
s=s.replace('''    # Ordinary participant turns should usually hold more than two voices, but\n    # not force a four-person chorus on every single message.''','''    # Allen now has explicit high conversational gravity: all four voices stay\n    # with his newest turn for the beat.''')
s=s.replace('require("rank 1 responds to ordinary Allen at least 85 percent", rates[1] >= .85, rates)','require("rank 1 always responds to ordinary Allen", rates[1] == 1.0, rates)')
s=s.replace('require("rank 2 responds to ordinary Allen often", .55 <= rates[2] <= .80, rates)','require("rank 2 always responds to ordinary Allen", rates[2] == 1.0, rates)')
s=s.replace('require("rank 3 sometimes responds to ordinary Allen", .25 <= rates[3] <= .55, rates)','require("rank 3 always responds to ordinary Allen", rates[3] == 1.0, rates)')
p.write_text(s)

p=ROOT/'scripts/room_allen_two_voice_sim.py'; s=p.read_text()
s=s.replace('''def second_voice_expected(key: str) -> bool:\n    # Rank 1 now stays with an ordinary Allen turn about 90% of the time.\n    # Determinism keeps a replayed beat on the same routing decision.\n    return hashlib.sha256(f"allen-responsive:1:{key}".encode()).digest()[0] < 230''','''def second_voice_expected(key: str) -> bool:\n    return True''')
# Remove the obsolete negative-route assertions.
s=s.replace('''    negative = pick_key(False)\n''','')
start='''    no_payload, no_expr = run_rank1(core, negative)\n    require(\n        "unselected rank-1 voice remains free to follow the first AI reply",\n        ((no_payload.get("event") or {}).get("speaker") == "mara"),\n        no_payload.get("event"),\n    )\n    require("unselected rank-1 voice is not forcibly redirected to Allen", no_expr.get("target") == "mara", no_expr)\n\n    ratio = sum(second_voice_expected(f"distribution-{i}") for i in range(4096)) / 4096\n    require("rank-1 deterministic gate is approximately 90 percent", 0.88 <= ratio <= 0.92, ratio)'''
repl='''    ratio = sum(second_voice_expected(f"distribution-{i}") for i in range(4096)) / 4096\n    require("rank-1 Allen gravity is 100 percent", ratio == 1.0, ratio)'''
assert start in s, 'rank1 regression source mismatch'
s=s.replace(start,repl,1)
p.write_text(s)

print('PASS: guarded Room tuning applied')
