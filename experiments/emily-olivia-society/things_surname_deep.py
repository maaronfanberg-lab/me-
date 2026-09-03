#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

import things_falcon_bridge_base as base

MAX_NAMES = 240
SOURCE_TIMEOUT = 12
USER_AGENT = "Things-Universe-v24/1.0 deep-surname-sweep"


def is_surname_term(term: str) -> bool:
    s = str(term or "").strip()
    return bool(re.fullmatch(r"[A-Za-zÀ-ÖØ-öø-ÿ'’.-]{2,48}", s))


def _surname(name: Any) -> str:
    s = re.sub(r"[^0-9A-Za-zÀ-ÖØ-öø-ÿ'’.-]+", " ", str(name or "")).strip()
    parts = [x for x in s.split() if x]
    return parts[-1].casefold() if parts else ""


def _clean_name(name: Any, term: str) -> str:
    s = base.text_clean(name, 100)
    s = re.sub(r"\s+", " ", s).strip(" ,;:()[]{}")
    if _surname(s) != term.casefold():
        return ""
    parts = s.split()
    if len(parts) < 2 or len(parts) > 8:
        return ""
    if any(re.search(r"\d|https?://|@", p, re.I) for p in parts):
        return ""
    return s


def _names_from_values(value: Any, term: str) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        for chunk in re.split(r"[;|\n]", value):
            name = _clean_name(chunk, term)
            if name:
                out.append(name)
    elif isinstance(value, list):
        for x in value:
            out.extend(_names_from_values(x, term))
    elif isinstance(value, dict):
        for k, v in value.items():
            if re.search(r"author|creator|personal|person|name", str(k), re.I):
                out.extend(_names_from_values(v, term))
    return out


def _http_json(url: str, timeout: int = SOURCE_TIMEOUT, headers: dict[str, str] | None = None) -> Any:
    h = {"Accept": "application/json", "User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _http_text(url: str, timeout: int = SOURCE_TIMEOUT, headers: dict[str, str] | None = None) -> str:
    h = {"User-Agent": USER_AGENT}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _rows(source: str, names: list[str], records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    seen = set()
    clean = []
    for n in names:
        k = n.casefold()
        if not n or k in seen:
            continue
        seen.add(k)
        clean.append(n)
        if len(clean) >= MAX_NAMES:
            break
    return {"source": source, "names": clean, "records": (records or [])[:80]}


def wikitree(term: str) -> dict[str, Any]:
    params = {
        "action": "searchPerson", "LastName": term, "lastNameMatch": "all", "limit": 100,
        "fields": "Id,Name,FirstName,MiddleName,RealName,LastNameAtBirth,LastNameCurrent,BirthDate,DeathDate,BirthLocation,DeathLocation,Father,Mother",
        "appId": "ThingsUniverseV24",
    }
    data = base.get_json("https://api.wikitree.com/api.php?" + urllib.parse.urlencode(params), timeout=SOURCE_TIMEOUT) or []
    payload = data[0] if isinstance(data, list) and data else data
    matches = payload.get("matches", []) if isinstance(payload, dict) else []
    names, records = [], []
    for p in matches[:100]:
        if not isinstance(p, dict):
            continue
        first = base.text_clean(p.get("RealName") or p.get("FirstName"), 50)
        middle = base.text_clean(p.get("MiddleName"), 40)
        last = base.text_clean(p.get("LastNameCurrent") or p.get("LastNameAtBirth"), 60)
        name = _clean_name(" ".join(x for x in (first, middle, last) if x), term)
        if name:
            names.append(name)
            records.append(p)
    return _rows("WikiTree", names, records)


def wikidata(term: str) -> dict[str, Any]:
    search = base.get_json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode({
        "origin": "*", "action": "wbsearchentities", "format": "json", "language": "en", "type": "item", "limit": 12, "search": term,
    }), timeout=SOURCE_TIMEOUT) or {}
    qid = ""
    for hit in search.get("search", []):
        if str(hit.get("label") or "").casefold() == term.casefold() and "family name" in str(hit.get("description") or "").casefold():
            qid = str(hit.get("id") or "")
            break
    if not qid:
        return _rows("Wikidata family-name index", [])
    sparql = f'''SELECT ?person ?personLabel WHERE {{ ?person wdt:P734 wd:{qid}. SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }} }} LIMIT {MAX_NAMES}'''
    data = base.get_json("https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": sparql, "format": "json"}), timeout=SOURCE_TIMEOUT) or {}
    names = []
    records = []
    for b in data.get("results", {}).get("bindings", []):
        name = _clean_name(((b.get("personLabel") or {}).get("value")), term)
        if name:
            names.append(name)
            records.append({"name": name, "entity": ((b.get("person") or {}).get("value"))})
    return _rows("Wikidata family-name index", names, records)


def openalex(term: str) -> dict[str, Any]:
    data = base.get_json("https://api.openalex.org/authors?" + urllib.parse.urlencode({"search": term, "per-page": 100}), timeout=SOURCE_TIMEOUT) or {}
    names, records = [], []
    for x in data.get("results", [])[:100]:
        name = _clean_name(x.get("display_name"), term)
        if name:
            names.append(name)
            records.append({"name": name, "id": x.get("id"), "works_count": x.get("works_count")})
    return _rows("OpenAlex", names, records)


def crossref(term: str) -> dict[str, Any]:
    data = base.get_json("https://api.crossref.org/works?" + urllib.parse.urlencode({"query.author": term, "rows": 100, "select": "DOI,title,author,published,type"}), timeout=SOURCE_TIMEOUT) or {}
    names, records = [], []
    for x in ((data.get("message") or {}).get("items") or [])[:100]:
        for a in x.get("author", []) or []:
            name = _clean_name(" ".join(filter(None, [a.get("given"), a.get("family")])), term)
            if name:
                names.append(name)
                records.append({"name": name, "doi": x.get("DOI"), "title": (x.get("title") or [""])[0]})
    return _rows("Crossref", names, records)


def openlibrary(term: str) -> dict[str, Any]:
    data = base.get_json("https://openlibrary.org/search.json?" + urllib.parse.urlencode({"q": term, "limit": 100, "fields": "key,title,author_name,first_publish_year"}), timeout=SOURCE_TIMEOUT) or {}
    names, records = [], []
    for x in data.get("docs", [])[:100]:
        for raw in x.get("author_name", []) or []:
            name = _clean_name(raw, term)
            if name:
                names.append(name)
                records.append({"name": name, "title": x.get("title"), "key": x.get("key")})
    return _rows("Open Library", names, records)


def google_books(term: str) -> dict[str, Any]:
    data = base.get_json("https://www.googleapis.com/books/v1/volumes?" + urllib.parse.urlencode({"q": f"inauthor:{term}", "maxResults": 40}), timeout=SOURCE_TIMEOUT) or {}
    names, records = [], []
    for x in data.get("items", [])[:40]:
        info = x.get("volumeInfo") or {}
        for raw in info.get("authors", []) or []:
            name = _clean_name(raw, term)
            if name:
                names.append(name)
                records.append({"name": name, "title": info.get("title"), "id": x.get("id")})
    return _rows("Google Books", names, records)


def pubmed(term: str) -> dict[str, Any]:
    search = _http_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode({
        "db": "pubmed", "term": f"{term}[Author]", "retmode": "json", "retmax": 100,
    }))
    ids = ((search.get("esearchresult") or {}).get("idlist") or [])[:100]
    if not ids:
        return _rows("PubMed", [])
    xml = _http_text("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}), timeout=SOURCE_TIMEOUT)
    root = ET.fromstring(xml)
    names, records = [], []
    for art in root.findall(".//PubmedArticle"):
        title = "".join(art.findtext(".//ArticleTitle") or "")
        for a in art.findall(".//Author"):
            last = a.findtext("LastName") or ""
            fore = a.findtext("ForeName") or a.findtext("Initials") or ""
            name = _clean_name(f"{fore} {last}", term)
            if name:
                names.append(name)
                records.append({"name": name, "title": base.text_clean(title, 180)})
    return _rows("PubMed", names, records)


def semantic_scholar(term: str) -> dict[str, Any]:
    data = base.get_json("https://api.semanticscholar.org/graph/v1/author/search?" + urllib.parse.urlencode({"query": term, "limit": 100, "fields": "name,url,paperCount"}), timeout=SOURCE_TIMEOUT) or {}
    names, records = [], []
    for x in data.get("data", [])[:100]:
        name = _clean_name(x.get("name"), term)
        if name:
            names.append(name)
            records.append({"name": name, "id": x.get("authorId"), "paper_count": x.get("paperCount")})
    return _rows("Semantic Scholar", names, records)


def dblp(term: str) -> dict[str, Any]:
    data = base.get_json("https://dblp.org/search/author/api?" + urllib.parse.urlencode({"q": term, "h": 100, "format": "json"}), timeout=SOURCE_TIMEOUT) or {}
    hits = (((data.get("result") or {}).get("hits") or {}).get("hit") or [])
    names, records = [], []
    for h in hits[:100]:
        info = h.get("info") or {}
        name = _clean_name(info.get("author"), term)
        if name:
            names.append(name)
            records.append({"name": name, "url": info.get("url")})
    return _rows("DBLP", names, records)


def viaf(term: str) -> dict[str, Any]:
    data = base.get_json("https://viaf.org/viaf/AutoSuggest?" + urllib.parse.urlencode({"query": term}), timeout=SOURCE_TIMEOUT) or {}
    names, records = [], []
    for x in data.get("result", []) or []:
        name = _clean_name(x.get("term"), term)
        if name:
            names.append(name)
            records.append({"name": name, "viafid": x.get("viafid")})
    return _rows("VIAF", names, records)


def loc(term: str) -> dict[str, Any]:
    data = base.get_json("https://www.loc.gov/search/?" + urllib.parse.urlencode({"q": term, "fo": "json", "c": 100}), timeout=SOURCE_TIMEOUT) or {}
    names, records = [], []
    for x in data.get("results", [])[:100]:
        values = []
        for key in ("contributor", "contributors", "creator"):
            values.extend(_names_from_values(x.get(key), term))
        for name in values:
            names.append(name)
            records.append({"name": name, "title": x.get("title"), "id": x.get("id")})
    return _rows("Library of Congress", names, records)


def internet_archive(term: str) -> dict[str, Any]:
    params = [("q", term), ("rows", "100"), ("page", "1"), ("output", "json"), ("fl[]", "identifier"), ("fl[]", "title"), ("fl[]", "creator")]
    data = base.get_json("https://archive.org/advancedsearch.php?" + urllib.parse.urlencode(params), timeout=SOURCE_TIMEOUT) or {}
    names, records = [], []
    for x in ((data.get("response") or {}).get("docs") or [])[:100]:
        for name in _names_from_values(x.get("creator"), term):
            names.append(name)
            records.append({"name": name, "identifier": x.get("identifier"), "title": x.get("title")})
    return _rows("Internet Archive", names, records)


def familysearch(term: str) -> dict[str, Any]:
    token = (getattr(base, "os", None) and base.os.environ.get("FAMILYSEARCH_ACCESS_TOKEN", "").strip()) or ""
    if not token:
        return _rows("FamilySearch", [])
    data = base.get_json(
        "https://api.familysearch.org/platform/tree/search?" + urllib.parse.urlencode({"q": f"surname:{term}", "count": 100}),
        timeout=SOURCE_TIMEOUT,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/x-gedcomx-v1+json"},
    ) or {}
    names, records = [], []
    for entry in data.get("entries", [])[:100]:
        gx = ((entry.get("content") or {}).get("gedcomx") or {})
        for p in gx.get("persons", []) or []:
            display = p.get("display") or {}
            name = _clean_name(display.get("name"), term)
            if name:
                names.append(name)
                records.append({"name": name, "lifespan": display.get("lifespan"), "birth": display.get("birthDate"), "death": display.get("deathDate")})
    return _rows("FamilySearch", names, records)


def united_nations(term: str) -> dict[str, Any]:
    # UN Digital Library's documented Invenio search API supports recjson output.
    url = "https://digitallibrary.un.org/search?" + urllib.parse.urlencode({"p": term, "of": "recjson", "rg": 100, "jrec": 1})
    data = _http_json(url, timeout=SOURCE_TIMEOUT)
    records = data if isinstance(data, list) else (data.get("records", []) if isinstance(data, dict) else [])
    names, out_records = [], []
    for rec in records[:100]:
        if not isinstance(rec, dict):
            continue
        local = []
        for k, v in rec.items():
            if re.search(r"author|creator|personal|person|name", str(k), re.I):
                local.extend(_names_from_values(v, term))
        for name in local:
            names.append(name)
            out_records.append({"name": name, "record": rec.get("recid") or rec.get("id")})
    return _rows("United Nations Digital Library", names, out_records)


def geneanet_public(term: str) -> dict[str, Any]:
    # Best-effort public HTML search. It may occasionally block automated clients;
    # failure is harmless because the rest of the sweep continues.
    url = "https://en.geneanet.org/fonds/individus/?" + urllib.parse.urlencode({"go": 1, "nom": term})
    html = _http_text(url, timeout=SOURCE_TIMEOUT)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    pattern = re.compile(rf"\b([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’.-]+(?:\s+[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ'’.-]+){{0,3}}\s+{re.escape(term)})\b", re.I)
    names = []
    for m in pattern.finditer(text):
        name = _clean_name(m.group(1), term)
        if name:
            names.append(name)
    return _rows("Geneanet public search", names)


GATHERERS: tuple[Callable[[str], dict[str, Any]], ...] = (
    wikitree, wikidata, familysearch, geneanet_public,
    openalex, crossref, pubmed, semantic_scholar, dblp,
    openlibrary, google_books, viaf, loc, internet_archive, united_nations,
)


def deep_surname_sweep(term: str) -> dict[str, Any]:
    if not is_surname_term(term):
        return {"term": term, "relations": [], "sources": [], "counts": {}}
    blocks: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(12, len(GATHERERS)), thread_name_prefix="surname-deep") as pool:
        future_map = {pool.submit(fn, term): fn for fn in GATHERERS}
        for future in as_completed(future_map):
            fn = future_map[future]
            try:
                block = future.result()
                if block.get("names"):
                    blocks.append(block)
            except Exception as exc:
                print(f"Deep surname source {fn.__name__} failed: {type(exc).__name__}: {exc}", flush=True)

    by_name: dict[str, dict[str, Any]] = {}
    for block in blocks:
        source = str(block.get("source") or "")
        for raw in block.get("names", []) or []:
            name = _clean_name(raw, term)
            if not name:
                continue
            k = name.casefold()
            row = by_name.setdefault(k, {"label": name, "sources": []})
            if source and source not in row["sources"]:
                row["sources"].append(source)

    relations = []
    for row in sorted(by_name.values(), key=lambda r: (-len(r["sources"]), r["label"].casefold()))[:MAX_NAMES]:
        relations.append({
            "label": row["label"],
            "relation": "shares surname",
            "confidence": 0.99,
            "sources": row["sources"][:8] or ["exact surname match"],
            "kind": "surname",
            "note": "Exact surname match; specific kinship requires family evidence.",
        })
    return {
        "term": term,
        "relations": relations,
        "sources": sorted({str(b.get("source")) for b in blocks if b.get("source")}),
        "counts": {str(b.get("source")): len(b.get("names") or []) for b in blocks},
    }
