#!/usr/bin/env python3
from __future__ import annotations

import time
import urllib.error
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any

import things_falcon_bridge as base
from bitnet_server import request_chat

EVIDENCE_WINDOW_SECONDS = 12.0
MAX_RELATIONS = 6


def gather_parallel(term: str) -> list[dict[str, Any]]:
    """Attempt every configured source concurrently and keep timely evidence."""
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


def parse_tsv(text: str, term: str, allowed_sources: set[str]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip().strip("` ")
        if not line or line.lower().startswith(("label\t", "label |", "relation")):
            continue
        parts = [part.strip() for part in line.split("\t")]
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


def enrich(term: str, context: list[str] | None = None) -> dict[str, Any]:
    started = time.monotonic()
    evidence = gather_parallel(term)
    compact = base.compact_evidence(evidence, budget=3600)
    allowed_sources = {str(item.get("source")) for item in compact if item.get("source")}
    if not compact:
        return {
            "term": term,
            "relations": [],
            "evidence_sources": [],
            "engine": "Falcon3-10B-Instruct-1.58bit via BitNet",
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }

    prompt = {
        "term": term,
        "context": (context or [])[:6],
        "evidence": compact,
    }
    system = (
        "You are a graph relation synthesizer. Use only the supplied evidence. "
        "Return at most 6 lines and nothing else. Each line MUST be exactly: "
        "LABEL<TAB>RELATION<TAB>CONFIDENCE<TAB>SOURCE1,SOURCE2. "
        "CONFIDENCE is 0 to 1. Source names must exactly match supplied source names. "
        "Shared surname is valid name-relatedness but never proof of blood relationship. "
        "Do not invent people, genealogy, dates, etymology, or citations. "
        "Prefer useful specific edges: surname variants, shared surname, origin, geography, lineage, derivation, influence, scholarship, structure, or causality when evidence supports them."
    )
    answer = request_chat(
        system,
        base.json.dumps(prompt, ensure_ascii=False, separators=(",", ":")),
        96,
        0.0,
        timeout=120,
    )
    relations = parse_tsv(answer, term, allowed_sources)
    return {
        "term": term,
        "relations": relations,
        "evidence_sources": sorted(allowed_sources),
        "engine": "Falcon3-10B-Instruct-1.58bit via BitNet",
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


def main() -> int:
    token = base.oidc_token()
    token_at = time.monotonic()
    print("Things Falcon bridge v2 is polling the Cloudflare relay.", flush=True)
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
                    result = enrich(term, [str(x)[:80] for x in context])
                    base.complete(token, job_id, result=result)
                    print(
                        f"Things v2 enriched: {term} -> {len(result['relations'])} relations "
                        f"from {len(result['evidence_sources'])} sources in {result['elapsed_seconds']}s",
                        flush=True,
                    )
                except Exception as exc:
                    base.complete(token, job_id, error=f"{type(exc).__name__}: {str(exc)[:300]}")
                    print(f"Things v2 enrichment failed for {term}: {exc}", flush=True)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                token = base.oidc_token()
                token_at = time.monotonic()
            time.sleep(base.POLL_SECONDS)
        except Exception as exc:
            print(f"Things v2 bridge poll error: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(base.POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
