#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import urllib.error
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Callable

import things_falcon_bridge_base as base
from bitnet_server import request_chat

EVIDENCE_WINDOW_SECONDS = 12.0
MAX_RELATIONS = 10


def gather_parallel(term: str) -> list[dict[str, Any]]:
    """Attempt every configured evidence source concurrently and retain timely answers."""
    order = {fn.__name__: i for i, fn in enumerate(base.GATHERERS)}
    collected: list[tuple[int, dict[str, Any]]] = []
    pool = ThreadPoolExecutor(max_workers=max(1, len(base.GATHERERS)), thread_name_prefix="things-evidence")
    futures = {pool.submit(fn, term): fn for fn in base.GATHERERS}
    pending = set(futures)
    deadline = time.monotonic() + EVIDENCE_WINDOW_SECONDS
    try:
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
            if not done:
                break
            for future in done:
                fn = futures[future]
                try:
                    item = future.result()
                    if item and item.get("items"):
                        collected.append((order[fn.__name__], item))
                except Exception as exc:
                    print(f"Things evidence source {fn.__name__} failed: {type(exc).__name__}: {exc}", flush=True)
    finally:
        for future in pending:
            future.cancel()
        pool.shutdown(wait=False, cancel_futures=True)
    collected.sort(key=lambda row: row[0])
    return [item for _, item in collected]


def _name_has_surname(name: Any, term: str) -> bool:
    clean = re.sub(r"[^0-9A-Za-zÀ-ÖØ-öø-ÿ'’-]+", " ", str(name or "")).strip()
    parts = [x for x in clean.split() if x]
    return bool(parts) and parts[-1].casefold() == term.strip().casefold()


def _relation(label: Any, relation: str, confidence: float, source: str) -> dict[str, Any] | None:
    text = base.text_clean(label, 70)
    if not text:
        return None
    return {
        "label": text,
        "relation": relation,
        "confidence": confidence,
        "sources": [source],
        "note": "",
    }


def direct_relations(term: str, evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn explicit source records into safe graph edges without waiting for the LLM."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def add(row: dict[str, Any] | None) -> None:
        if not row:
            return
        label = str(row.get("label") or "").strip()
        relation = str(row.get("relation") or "").strip()
        if not label or not relation or label.casefold() == term.casefold():
            return
        key = (label.casefold(), relation.casefold())
        if key in seen:
            return
        seen.add(key)
        out.append(row)

    for block in evidence:
        source = str(block.get("source") or "")
        items = block.get("items") or []

        if source == "WikiTree":
            for item in items:
                last = item.get("LastNameCurrent") or item.get("LastNameAtBirth")
                if str(last or "").casefold() != term.casefold():
                    continue
                first = base.text_clean(item.get("FirstName"), 50)
                label = " ".join(x for x in (first, base.text_clean(last, 60)) if x)
                if label:
                    add(_relation(label, "shares surname", 0.93, source))

        elif source == "FamilySearch":
            for item in items:
                name = item.get("name")
                if _name_has_surname(name, term):
                    add(_relation(name, "shares surname in family-history record", 0.92, source))

        elif source == "Wikidata":
            for item in items:
                label = item.get("label")
                if _name_has_surname(label, term):
                    add(_relation(label, "has surname", 0.84, source))

        elif source == "OpenAlex":
            for item in items:
                if item.get("type") != "author":
                    continue
                name = item.get("name")
                if _name_has_surname(name, term):
                    add(_relation(name, "surname used by scholarly author", 0.88, source))

        elif source == "Crossref":
            for item in items:
                for name in item.get("authors") or []:
                    if _name_has_surname(name, term):
                        add(_relation(name, "surname used by published author", 0.88, source))

        elif source == "Open Library":
            for item in items:
                for name in item.get("authors") or []:
                    if _name_has_surname(name, term):
                        add(_relation(name, "surname used by book author", 0.86, source))

        if len(out) >= MAX_RELATIONS:
            break

    return out[:MAX_RELATIONS]


def parse_tsv(text: str, term: str, allowed_sources: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip().strip("` ")
        if not line:
            continue
        parts = [part.strip() for part in line.split("\t")]
        if len(parts) != 4 and "|" in line:
            parts = [part.strip() for part in line.split("|")]
        if len(parts) != 4:
            continue
        label, relation, raw_confidence, raw_sources = parts
        label = base.text_clean(label, 70)
        relation = base.text_clean(relation, 70)
        if not label or not relation or label.lower() == term.lower():
            continue
        try:
            confidence = max(0.0, min(1.0, float(raw_confidence)))
        except Exception:
            continue
        sources: list[str] = []
        for source in raw_sources.split(","):
            name = base.text_clean(source, 50)
            if name in allowed_sources and name not in sources:
                sources.append(name)
        if not sources:
            continue
        key = (label.lower(), relation.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "label": label,
            "relation": relation,
            "confidence": confidence,
            "sources": sources[:4],
            "note": "",
        })
        if len(out) >= MAX_RELATIONS:
            break
    return out


def merge_relations(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for group in groups:
        for row in group:
            key = (str(row.get("label") or "").casefold(), str(row.get("relation") or "").casefold())
            if not all(key) or key in seen:
                continue
            seen.add(key)
            out.append(row)
            if len(out) >= MAX_RELATIONS:
                return out
    return out


def enrich(
    term: str,
    context: list[str] | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    evidence = gather_parallel(term)
    compact = base.compact_evidence(evidence, budget=3600)
    allowed_sources = {str(item.get("source")) for item in compact if item.get("source")}
    explicit = direct_relations(term, compact)

    evidence_result = {
        "term": term,
        "relations": explicit,
        "evidence_sources": sorted(allowed_sources),
        "engine": "multi-source evidence; Falcon3-10B-Instruct-1.58bit pending",
        "phase": "evidence",
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    if progress_callback:
        progress_callback(evidence_result)

    if not compact:
        return evidence_result | {"engine": "multi-source evidence", "phase": "done"}

    prompt = {
        "term": term,
        "context": (context or [])[:6],
        "evidence": compact,
    }
    system = (
        "Use only the supplied evidence to make graph relations. Return at most 6 lines and nothing else. "
        "Each line must be LABEL<TAB>RELATION<TAB>CONFIDENCE<TAB>SOURCE1,SOURCE2. "
        "Confidence is 0 to 1 and source names must exactly match supplied source names. "
        "Shared surname is valid name-relatedness, never proof of blood relationship. "
        "Do not invent people, genealogy, dates, etymology, or citations. Prefer useful specific edges."
    )
    try:
        answer = request_chat(
            system,
            json.dumps(prompt, ensure_ascii=False, separators=(",", ":")),
            96,
            0.0,
            timeout=180,
        )
        inferred = parse_tsv(answer, term, allowed_sources)
    except Exception as exc:
        print(f"Things Falcon synthesis deferred for {term}: {type(exc).__name__}: {exc}", flush=True)
        inferred = []

    relations = merge_relations(explicit, inferred)
    return {
        "term": term,
        "relations": relations,
        "evidence_sources": sorted(allowed_sources),
        "engine": "Falcon3-10B-Instruct-1.58bit via BitNet + multi-source evidence",
        "phase": "done",
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def send_progress(token: str, job_id: str, result: dict[str, Any]) -> None:
    base.post_json(
        base.WORKER + "/api/things/progress",
        {"id": job_id, "result": result},
        headers={"Authorization": f"Bearer {token}"},
    )


def main() -> int:
    token = base.oidc_token()
    token_at = time.monotonic()
    print("Things Falcon bridge v3 is polling the Cloudflare relay.", flush=True)
    while True:
        try:
            if time.monotonic() - token_at > 240:
                token = base.oidc_token()
                token_at = time.monotonic()
            jobs = base.pending(token)
            if not jobs:
                time.sleep(base.POLL_SECONDS)
                continue
            for job in jobs[:4]:
                job_id = str(job.get("id", ""))
                term = str(job.get("term", "")).strip()[:80]
                context = job.get("context") if isinstance(job.get("context"), list) else []
                if not job_id or not term:
                    continue
                try:
                    result = enrich(
                        term,
                        [str(x)[:80] for x in context],
                        progress_callback=lambda partial, t=token, j=job_id: send_progress(t, j, partial),
                    )
                    base.complete(token, job_id, result=result)
                    print(
                        f"Things v3 enriched: {term} -> {len(result['relations'])} relations "
                        f"from {len(result['evidence_sources'])} sources in {result['elapsed_seconds']}s",
                        flush=True,
                    )
                except Exception as exc:
                    base.complete(token, job_id, error=f"{type(exc).__name__}: {str(exc)[:300]}")
                    print(f"Things v3 enrichment failed for {term}: {exc}", flush=True)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                token = base.oidc_token()
                token_at = time.monotonic()
            time.sleep(base.POLL_SECONDS)
        except Exception as exc:
            print(f"Things v3 bridge poll error: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(base.POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
