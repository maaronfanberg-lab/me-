#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from bitnet_server import request_chat

WORKER = os.environ.get("THINGS_RELAY_BASE", "https://room-live-mirror.dfp6k69dw5.workers.dev").rstrip("/")
AUDIENCE = os.environ.get("THINGS_OIDC_AUDIENCE", "room-live-mirror")
POLL_SECONDS = float(os.environ.get("THINGS_POLL_SECONDS", "2.0"))
USER_AGENT = "Things-Universe-v24/1.0 (public knowledge enrichment)"
EVIDENCE_CHAR_BUDGET = 4300


def get_json(url: str, timeout: int = 12, headers: dict[str, str] | None = None, quiet: bool = True) -> Any:
    h = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        if quiet:
            return None
        raise


def post_json(url: str, payload: Any, timeout: int = 15, headers: dict[str, str] | None = None) -> Any:
    h = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def oidc_token() -> str:
    base = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")
    bearer = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")
    if not base or not bearer:
        raise RuntimeError("GitHub Actions OIDC environment is unavailable")
    sep = "&" if "?" in base else "?"
    data = get_json(
        base + sep + urllib.parse.urlencode({"audience": AUDIENCE}),
        headers={"Authorization": f"Bearer {bearer}"},
        quiet=False,
    )
    token = data.get("value") if isinstance(data, dict) else None
    if not token:
        raise RuntimeError("GitHub Actions OIDC token request returned no token")
    return str(token)


def text_clean(value: Any, limit: int = 240) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    text = re.sub(r"\{\{.*?\}\}", " ", text, flags=re.S)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def source(name: str, rows: list[dict[str, Any]], limit: int = 8) -> dict[str, Any]:
    return {"source": name, "items": rows[:limit]}


def conceptnet(term: str) -> dict[str, Any]:
    key = re.sub(r"\s+", "_", term.strip().lower())
    url = "https://api.conceptnet.io/query?" + urllib.parse.urlencode({"node": f"/c/en/{key}", "limit": 28})
    data = get_json(url) or {}
    rows = []
    for edge in data.get("edges", [])[:28]:
        start, end = edge.get("start", {}), edge.get("end", {})
        rel = str(edge.get("rel", {}).get("label", "related to"))
        a, b = start.get("label"), end.get("label")
        if a and b:
            rows.append({"a": text_clean(a, 80), "r": text_clean(rel, 60), "b": text_clean(b, 80)})
    return source("ConceptNet", rows, 7)


def wikidata(term: str) -> dict[str, Any]:
    q = urllib.parse.urlencode({"origin": "*", "action": "wbsearchentities", "format": "json", "language": "en", "type": "item", "limit": 8, "search": term})
    data = get_json("https://www.wikidata.org/w/api.php?" + q) or {}
    rows = []
    for hit in data.get("search", [])[:8]:
        rows.append({"label": text_clean(hit.get("label"), 90), "description": text_clean(hit.get("description"), 150), "id": hit.get("id")})
    return source("Wikidata", rows, 5)


def wikipedia(term: str) -> dict[str, Any]:
    q = urllib.parse.urlencode({"origin": "*", "action": "query", "format": "json", "redirects": 1, "prop": "extracts|categories", "exintro": 1, "explaintext": 1, "cllimit": 24, "titles": term})
    data = get_json("https://en.wikipedia.org/w/api.php?" + q) or {}
    pages = list((data.get("query", {}).get("pages") or {}).values())
    if not pages:
        return source("Wikipedia", [])
    p = pages[0]
    row = {
        "title": text_clean(p.get("title"), 90),
        "summary": text_clean(p.get("extract"), 360),
        "categories": [text_clean(x.get("title", "").replace("Category:", ""), 80) for x in p.get("categories", [])[:8]],
    }
    return source("Wikipedia", [row], 1)


def wiktionary(term: str) -> dict[str, Any]:
    q = urllib.parse.urlencode({"origin": "*", "action": "parse", "format": "json", "prop": "wikitext", "page": term, "redirects": 1})
    data = get_json("https://en.wiktionary.org/w/api.php?" + q) or {}
    raw = (((data.get("parse") or {}).get("wikitext") or {}).get("*")) or ""
    snippets = []
    for heading in ("Etymology", "Alternative forms", "Proper noun", "Surname"):
        m = re.search(rf"==+\s*{re.escape(heading)}\s*==+(.*?)(?=\n==+[^=]|\Z)", raw, flags=re.I | re.S)
        if m:
            snippets.append(f"{heading}: {text_clean(m.group(1), 420)}")
    return source("Wiktionary", [{"entry": term, "text": " | ".join(snippets)[:850]}] if snippets else [], 1)


def wikitree(term: str) -> dict[str, Any]:
    params = {
        "action": "searchPerson",
        "LastName": term,
        "lastNameMatch": "all",
        "limit": 12,
        "fields": "Name,FirstName,LastNameAtBirth,LastNameCurrent,BirthDate,DeathDate,BirthLocation,DeathLocation,Father,Mother",
    }
    data = get_json("https://api.wikitree.com/api.php?" + urllib.parse.urlencode(params))
    payload = data[0] if isinstance(data, list) and data else data
    matches = payload.get("matches", []) if isinstance(payload, dict) else []
    rows = []
    for p in matches[:12]:
        rows.append({k: p.get(k) for k in ("Name", "FirstName", "LastNameAtBirth", "LastNameCurrent", "BirthDate", "DeathDate", "BirthLocation", "DeathLocation", "Father", "Mother") if p.get(k) not in (None, "", 0)})
    return source("WikiTree", rows, 6)


def dbpedia(term: str) -> dict[str, Any]:
    query = f'''PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#> SELECT ?s ?label ?comment WHERE {{ ?s rdfs:label ?label . FILTER(lang(?label)='en') FILTER(lcase(str(?label)) = lcase({json.dumps(term)})) OPTIONAL {{ ?s rdfs:comment ?comment . FILTER(lang(?comment)='en') }} }} LIMIT 5'''
    url = "https://dbpedia.org/sparql?" + urllib.parse.urlencode({"query": query, "format": "application/sparql-results+json"})
    data = get_json(url) or {}
    rows = []
    for b in data.get("results", {}).get("bindings", [])[:5]:
        rows.append({"entity": text_clean(b.get("label", {}).get("value"), 90), "description": text_clean(b.get("comment", {}).get("value"), 260)})
    return source("DBpedia", rows, 3)


def openalex(term: str) -> dict[str, Any]:
    rows = []
    for endpoint in ("authors", "topics", "works"):
        url = f"https://api.openalex.org/{endpoint}?" + urllib.parse.urlencode({"search": term, "per-page": 3})
        data = get_json(url) or {}
        for x in data.get("results", [])[:3]:
            rows.append({"type": endpoint[:-1], "name": text_clean(x.get("display_name") or x.get("title"), 130), "id": x.get("id")})
    return source("OpenAlex", rows, 6)


def crossref(term: str) -> dict[str, Any]:
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode({"query": term, "rows": 4, "select": "DOI,title,author,published,type,subject"})
    data = get_json(url) or {}
    rows = []
    for x in ((data.get("message") or {}).get("items") or [])[:4]:
        authors = [" ".join(filter(None, [a.get("given"), a.get("family")])) for a in x.get("author", [])[:3]]
        rows.append({"title": text_clean((x.get("title") or [""])[0], 150), "authors": authors, "type": x.get("type"), "doi": x.get("DOI"), "subjects": x.get("subject", [])[:4]})
    return source("Crossref", rows, 3)


def openlibrary(term: str) -> dict[str, Any]:
    url = "https://openlibrary.org/search.json?" + urllib.parse.urlencode({"q": term, "limit": 4, "fields": "key,title,author_name,first_publish_year,subject"})
    data = get_json(url) or {}
    rows = []
    for x in data.get("docs", [])[:4]:
        rows.append({"title": text_clean(x.get("title"), 140), "authors": x.get("author_name", [])[:3], "year": x.get("first_publish_year"), "subjects": x.get("subject", [])[:5]})
    return source("Open Library", rows, 3)


def familysearch(term: str) -> dict[str, Any]:
    token = os.environ.get("FAMILYSEARCH_ACCESS_TOKEN", "").strip()
    if not token:
        return source("FamilySearch", [])
    query = urllib.parse.quote(f"surname:{term}")
    data = get_json(
        f"https://api.familysearch.org/platform/tree/search?q={query}&count=8",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/x-gedcomx-v1+json"},
    ) or {}
    rows = []
    for entry in data.get("entries", [])[:8]:
        content = entry.get("content", {}).get("gedcomx", {})
        for person in content.get("persons", [])[:2]:
            display = person.get("display", {})
            rows.append({"name": text_clean(display.get("name"), 100), "birth": text_clean(display.get("birthDate"), 50), "death": text_clean(display.get("deathDate"), 50), "lifespan": text_clean(display.get("lifespan"), 70)})
    return source("FamilySearch", rows, 6)


GATHERERS: tuple[Callable[[str], dict[str, Any]], ...] = (
    wikitree,
    wiktionary,
    wikidata,
    conceptnet,
    wikipedia,
    dbpedia,
    openalex,
    crossref,
    openlibrary,
    familysearch,
)


def gather(term: str) -> list[dict[str, Any]]:
    evidence = []
    for fn in GATHERERS:
        try:
            item = fn(term)
            if item.get("items"):
                evidence.append(item)
        except Exception as exc:
            print(f"Things evidence source {fn.__name__} failed: {type(exc).__name__}: {exc}", flush=True)
    return evidence


def compact_evidence(evidence: list[dict[str, Any]], budget: int = EVIDENCE_CHAR_BUDGET) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    used = 2
    # First pass gives every live source one item, so broad evidence does not get
    # crowded out by whichever endpoint happened to return the most rows.
    for item in evidence:
        rows = item.get("items") or []
        if not rows:
            continue
        candidate = {"source": item.get("source"), "items": [rows[0]]}
        size = len(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")))
        if used + size <= budget:
            out.append(candidate)
            used += size
    # Second pass fills remaining space round-robin.
    for round_index in range(1, 8):
        changed = False
        for original in evidence:
            rows = original.get("items") or []
            if round_index >= len(rows):
                continue
            target = next((x for x in out if x.get("source") == original.get("source")), None)
            if target is None:
                continue
            before = len(json.dumps(target, ensure_ascii=False, separators=(",", ":")))
            expanded = {"source": target["source"], "items": [*target["items"], rows[round_index]]}
            after = len(json.dumps(expanded, ensure_ascii=False, separators=(",", ":")))
            delta = after - before
            if used + delta <= budget:
                target["items"].append(rows[round_index])
                used += delta
                changed = True
        if not changed:
            break
    return out


def parse_relations(text: str, term: str, allowed_sources: set[str]) -> list[dict[str, Any]]:
    candidate = text.strip()
    match = re.search(r"\{.*\}", candidate, flags=re.S)
    if match:
        candidate = match.group(0)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    rows = data.get("relations", []) if isinstance(data, dict) else []
    out = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = text_clean(row.get("label"), 70)
        relation = text_clean(row.get("relation"), 70)
        if not label or not relation or label.lower() == term.lower():
            continue
        sources = []
        for raw_source in row.get("sources", []):
            name = text_clean(raw_source, 50)
            if name in allowed_sources and name not in sources:
                sources.append(name)
        if not sources:
            continue
        key = (label.lower(), relation.lower())
        if key in seen:
            continue
        seen.add(key)
        try:
            confidence = max(0.0, min(1.0, float(row.get("confidence", 0.5))))
        except Exception:
            confidence = 0.5
        out.append({"label": label, "relation": relation, "confidence": confidence, "sources": sources[:5], "note": text_clean(row.get("note"), 160)})
        if len(out) >= 14:
            break
    return out


def enrich(term: str, context: list[str] | None = None) -> dict[str, Any]:
    evidence = gather(term)
    compact = compact_evidence(evidence)
    allowed_sources = {str(x.get("source")) for x in compact if x.get("source")}
    prompt = {"term": term, "context": (context or [])[:8], "evidence": compact}
    system = (
        "You turn supplied evidence into a small graph. Return JSON only as "
        "{\"relations\":[{\"label\":str,\"relation\":str,\"confidence\":0..1,\"sources\":[str],\"note\":str}]}. "
        "Use only source names present in the evidence. Prefer specific defensible edges. Shared surname is valid name-relatedness, not proof of blood relation. "
        "Never invent people, dates, genealogy, etymology, or citations. Include lineage, derivation, influence, variants, geography, scholarship, structure, or causality only when evidence supports it."
    )
    user = json.dumps(prompt, ensure_ascii=False, separators=(",", ":"))
    answer = request_chat(system, user, 224, 0.1, timeout=45)
    relations = parse_relations(answer, term, allowed_sources)
    return {
        "term": term,
        "relations": relations,
        "evidence_sources": sorted(allowed_sources),
        "engine": "Falcon3-10B-Instruct-1.58bit via BitNet",
    }


def pending(token: str) -> list[dict[str, Any]]:
    data = get_json(WORKER + "/api/things/pending", headers={"Authorization": f"Bearer {token}"}, quiet=False) or {}
    return data.get("jobs", []) if isinstance(data, dict) else []


def complete(token: str, job_id: str, result: dict[str, Any] | None = None, error: str = "") -> None:
    post_json(WORKER + "/api/things/complete", {"id": job_id, "result": result, "error": error}, headers={"Authorization": f"Bearer {token}"})


def main() -> int:
    token = oidc_token()
    token_at = time.monotonic()
    print("Things Falcon bridge is polling the Cloudflare relay.", flush=True)
    while True:
        try:
            if time.monotonic() - token_at > 240:
                token = oidc_token()
                token_at = time.monotonic()
            jobs = pending(token)
            if not jobs:
                time.sleep(POLL_SECONDS)
                continue
            for job in jobs[:4]:
                job_id = str(job.get("id", ""))
                term = str(job.get("term", "")).strip()[:80]
                context = job.get("context") if isinstance(job.get("context"), list) else []
                if not job_id or not term:
                    continue
                try:
                    result = enrich(term, [str(x)[:80] for x in context])
                    complete(token, job_id, result=result)
                    print(f"Things enriched: {term} -> {len(result['relations'])} relations from {len(result['evidence_sources'])} sources", flush=True)
                except Exception as exc:
                    complete(token, job_id, error=f"{type(exc).__name__}: {str(exc)[:300]}")
                    print(f"Things enrichment failed for {term}: {exc}", flush=True)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                token = oidc_token()
                token_at = time.monotonic()
            time.sleep(POLL_SECONDS)
        except Exception as exc:
            print(f"Things bridge poll error: {type(exc).__name__}: {exc}", flush=True)
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
