#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from typing import Any, Callable

import things_falcon_bridge as family_bridge
import things_falcon_bridge_base as base
import things_falcon_bridge_v3 as v3
import things_surname_deep as deep
import things_sweden_genealogy as sweden_genealogy
import things_web_mentions as web_mentions

MAX_RELATIONS = 240
MAX_WEB_RELATIONS = 200


def _ends_with_surname(value: Any, term: str) -> bool:
    text = base.text_clean(value, 120)
    parts = [x for x in text.replace("-", " ").split() if x]
    return len(parts) >= 2 and parts[-1].strip(".,;:()[]{}\"'").casefold() == term.strip().casefold()


def _surname_supported(term: str, evidence: list[dict[str, Any]], context: list[str] | None) -> bool:
    if not deep.is_surname_term(term):
        return False
    if any(_ends_with_surname(value, term) for value in (context or [])):
        return True
    needle = term.strip().casefold()
    for block in evidence:
        source = str(block.get("source") or "")
        items = block.get("items") or []
        if source == "WikiTree":
            for item in items:
                last = item.get("LastNameCurrent") or item.get("LastNameAtBirth")
                if str(last or "").strip().casefold() == needle:
                    return True
        elif source == "FamilySearch":
            if any(_ends_with_surname(item.get("name"), term) for item in items):
                return True
        elif source == "Wiktionary":
            if "surname" in json.dumps(items, ensure_ascii=False).casefold():
                return True
        elif source == "Wikidata":
            for item in items:
                description = str(item.get("description") or "").casefold()
                if "surname" in description or "family name" in description:
                    return True
        elif source in {"OpenAlex", "Crossref", "Open Library"}:
            if term.casefold() in json.dumps(items, ensure_ascii=False).casefold():
                return True
    return False


def _web_rows(
    term: str,
    block: dict[str, Any],
    source_name: str | None = None,
    confidence: float = 0.78,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    needle = term.casefold()
    source = base.text_clean(source_name or block.get("source"), 70) or web_mentions.SOURCE_NAME
    for item in block.get("items") or []:
        title = base.text_clean(item.get("title") or item.get("url"), 70)
        url = base.text_clean(item.get("url"), 500)
        snippet = base.text_clean(item.get("snippet"), 280)
        hay = " ".join((title, url, snippet)).casefold()
        if not title or needle not in hay:
            continue
        key = (url or title).casefold()
        if key in seen:
            continue
        seen.add(key)
        index = base.text_clean(item.get("index"), 90) or source
        rows.append({
            "label": title,
            "relation": "web mention",
            "confidence": confidence,
            "sources": [source],
            "kind": "other",
            "note": " | ".join(x for x in (index, url) if x)[:500],
        })
        if len(rows) >= MAX_WEB_RELATIONS:
            break
    return rows


def enrich_web(
    term: str,
    context: list[str] | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    context = context or []
    evidence = v3.gather_parallel(term)
    compact = base.compact_evidence(evidence, budget=3600)
    falcon_sources = {str(item.get("source")) for item in compact if item.get("source")}
    display_sources = set(falcon_sources)

    basic = v3.direct_relations(term, compact)
    for row in basic:
        row.setdefault("kind", "surname" if "surname" in str(row.get("relation") or "").casefold() else "other")

    def send(phase: str, relations: list[dict[str, Any]], engine: str) -> None:
        if not progress_callback:
            return
        progress_callback({
            "term": term,
            "relations": relations[:MAX_RELATIONS],
            "evidence_sources": sorted(display_sources),
            "engine": engine,
            "phase": phase,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        })

    send(
        "evidence",
        basic,
        "multi-source evidence; deep surname + UNPAN/source web + Swedish genealogy + family walk + Falcon pending",
    )

    surname_mode = _surname_supported(term, evidence, context)
    deep_rows: list[dict[str, Any]] = []
    web_rows: list[dict[str, Any]] = []
    sweden_rows: list[dict[str, Any]] = []

    if surname_mode:
        try:
            sweep = deep.deep_surname_sweep(term)
            deep_rows = list(sweep.get("relations") or [])[:MAX_RELATIONS]
            display_sources.update(str(x) for x in (sweep.get("sources") or []) if x)
            if deep_rows:
                send(
                    "surname",
                    family_bridge.merge_relations(basic, deep_rows),
                    "deep surname sweep; UNPAN/source web + Swedish genealogy + family refinement + Falcon pending",
                )
        except Exception as exc:
            print(f"Deep surname sweep failed for {term}: {type(exc).__name__}: {exc}", flush=True)

        try:
            web_block = web_mentions.webwide_mentions(term)
            web_rows = _web_rows(term, web_block, web_mentions.SOURCE_NAME)
            if web_rows:
                display_sources.add(web_mentions.SOURCE_NAME)
                send(
                    "web",
                    family_bridge.merge_relations(basic, deep_rows, web_rows),
                    "deep surname sweep + UNPAN/source web; Swedish genealogy + family refinement + Falcon pending",
                )
        except Exception as exc:
            print(f"Web-wide mention sweep failed for {term}: {type(exc).__name__}: {exc}", flush=True)

        try:
            sweden_block = sweden_genealogy.sweden_genealogy_mentions(term)
            sweden_rows = _web_rows(
                term,
                sweden_block,
                sweden_genealogy.SOURCE_NAME,
                confidence=0.80,
            )
            if sweden_rows:
                display_sources.add(sweden_genealogy.SOURCE_NAME)
                send(
                    "sweden",
                    family_bridge.merge_relations(basic, deep_rows, web_rows, sweden_rows),
                    "deep surname sweep + UNPAN/source web + Swedish genealogy; family refinement + Falcon pending",
                )
        except Exception as exc:
            print(f"Swedish genealogy sweep failed for {term}: {type(exc).__name__}: {exc}", flush=True)

    family: list[dict[str, Any]] = []
    if "WikiTree" in falcon_sources:
        family = family_bridge.family_relations(
            term,
            compact,
            emit=lambda rows: send(
                "family",
                family_bridge.merge_relations(basic, deep_rows, rows, web_rows, sweden_rows),
                "deep surname + UNPAN/source web + Swedish genealogy + family refinement; Falcon pending",
            ),
        )

    if not compact:
        return {
            "term": term,
            "relations": family_bridge.merge_relations(basic, deep_rows, family, web_rows, sweden_rows),
            "evidence_sources": sorted(display_sources),
            "engine": "multi-source evidence + UNPAN/source web + Swedish genealogy",
            "phase": "done",
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }

    prompt = {
        "term": term,
        "context": context[:6],
        "evidence": compact,
        "explicit_family_relations": family[:20],
    }
    system = (
        "Use only the supplied evidence to make graph relations. Return at most 6 lines and nothing else. "
        "Each line must be LABEL<TAB>RELATION<TAB>CONFIDENCE<TAB>SOURCE1,SOURCE2. "
        "Confidence is 0 to 1 and source names must exactly match supplied source names. "
        "Explicit family relations are authoritative and must not be contradicted. "
        "Shared surname is valid name-relatedness, never proof of blood relationship. "
        "Do not invent people, genealogy, dates, etymology, or citations. Prefer useful specific edges."
    )
    try:
        answer = v3.request_chat(
            system,
            json.dumps(prompt, ensure_ascii=False, separators=(",", ":")),
            96,
            0.0,
            timeout=180,
        )
        inferred = v3.parse_tsv(answer, term, falcon_sources)
    except Exception as exc:
        print(f"Things Falcon synthesis deferred for {term}: {type(exc).__name__}: {exc}", flush=True)
        inferred = []

    relations = family_bridge.merge_relations(basic, deep_rows, family, web_rows, sweden_rows, inferred)
    return {
        "term": term,
        "relations": relations,
        "evidence_sources": sorted(display_sources),
        "engine": "Falcon3-10B-Instruct-1.58bit via BitNet + deep surname + UNPAN/source web + Swedish genealogy + kinship refinement",
        "phase": "done",
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


v3.enrich = enrich_web

if __name__ == "__main__":
    raise SystemExit(v3.main())
