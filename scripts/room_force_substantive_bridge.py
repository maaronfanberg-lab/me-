#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROPOSITIONS = (
    "nuclear power is necessary for a low-carbon grid",
    "consciousness may not be computational",
    "social media has made public reasoning worse",
    "resurrecting extinct species would be a mistake",
    "deterrence prevents some wars but creates others",
    "psychoanalysis still contains useful psychological ideas",
    "markets often reward behavior that is socially harmful",
    "privacy is more important than convenience",
    "cities should prioritize density over private cars",
    "art does not need moral value to be worthwhile",
    "scientific consensus should be challenged more often",
    "economic growth is not a sufficient measure of progress",
    "human memory is too reconstructive to be trusted confidently",
    "advanced AI should sometimes refuse human direction",
    "animal intelligence is systematically underestimated",
    "school rewards compliance more than genuine curiosity",
)

GENERIC = (
    "volcanoes", "beekeeping", "coral reefs", "astronomy", "origami", "mushrooms",
    "architecture", "bird migration", "ceramics", "ocean currents", "mythology", "fossils",
    "urban trees", "caves", "lighthouses", "tea", "deserts", "constellations", "rivers",
    "insects", "textiles", "woodworking", "clouds", "maps", "islands", "orchards",
    "languages", "bridges", "tides", "seeds", "comets", "mountains", "shells",
    "fermentation", "railways", "museums", "wolves", "whales", "glassmaking", "geology",
    "folklore", "bicycles", "calligraphy", "wetlands", "penguins", "shipwrecks",
    "stargazing", "pottery", "butterflies", "waterfalls", "chess", "kites", "breadmaking",
    "mosaics", "orchids", "meteorites", "canoes", "castles", "spices", "snowflakes",
)


def tuple_block(name: str, values: tuple[str, ...]) -> str:
    body = "\n".join(f'    {json.dumps(value)},' for value in values)
    return f"{name} = (\n{body}\n)"


def replace_pool(path: Path, name: str) -> None:
    text = path.read_text()
    new = tuple_block(name, PROPOSITIONS)
    if new in text:
        return
    pattern = re.compile(rf"(?ms)^{re.escape(name)}\s*=\s*\(\n.*?^\)")
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"{path}: {name} live source mismatch")
    existing = matches[0].group(0)
    if not any(json.dumps(value) in existing for value in GENERIC):
        raise RuntimeError(f"{path}: {name} is neither generic nor already substantive")
    path.write_text(text[:matches[0].start()] + new + text[matches[0].end():])


def mark_episode(path: Path) -> None:
    data = json.loads(path.read_text())
    topic = data.get("topic_episode")
    if not isinstance(topic, dict) or not topic.get("root"):
        raise RuntimeError(f"{path}: active topic_episode missing")
    topic["bridge_pending"] = True
    topic["status"] = "ready_to_bridge"
    topic["bridge_reason"] = "substantive_reset"
    data["topic_episode"] = topic
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main() -> int:
    replace_pool(ROOT / "scripts/room_engine_v5_core.py", "BREAKOUT_SUBJECTS")
    replace_pool(ROOT / "scripts/room_topic_bounded.py", "_AGE_BREAKOUT_SUBJECTS")
    mark_episode(ROOT / "room/state.json")
    mark_episode(ROOT / "room/cognitive_state.json")

    pulse = ROOT / "society/pulse-kick.txt"
    marker = "2026-08-22T23:15Z FORCE substantive Room bridge\n"
    existing = pulse.read_text()
    if marker not in existing:
        pulse.write_text(existing + marker)

    print("PASS: substantive breakout pools installed")
    print("PASS: current meta episode marked ready_to_bridge")
    print("PASS: Room restart marker added")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
