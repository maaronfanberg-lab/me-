#!/usr/bin/env python3
from __future__ import annotations

import json
import html
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Callable

SOURCE_NAME = "Swedish genealogy sources"
USER_AGENT = "Things-Universe-v24/1.0 (Swedish public genealogy discovery)"
MAX_ITEMS = 180
SEARCH_WINDOW_SECONDS = 9.0

# Public/no-cost Swedish genealogy and historical-person sources verified from
# the current services themselves and Sveriges Släktforskarförbund's 2026
# free-resource guide. The sweep searches the source domains for literal surname
# mentions and preserves the originating institution in every returned item.
SITE_LABELS: dict[str, str] = {
    "sok.riksarkivet.se": "Riksarkivet",
    "riksarkivet.se": "Riksarkivet",
    "slaktdata.org": "Släktdata",
    "register.slaktdata.org": "Släktdata",
    "rotter.se": "Rötter / Sveriges Släktforskarförbund",
    "forum.rotter.se": "Anbytarforum",
    "sokdatabas.soldatreg.se": "Centrala Soldatregistret",
    "soldatreg.se": "Centrala Soldatregistret",
    "blekingesf.se": "Blekinge Släktforskarförening",
    "lanspumpen.se": "Länspumpen / Sveriges skeppslista",
    "ep.liu.se": "Linköpings universitet E-Press databaser",
    "stadsarkivet.stockholm": "Stockholms stadsarkiv",
    "sok.stadsarkivet.stockholm.se": "Stockholms stadsarkiv",
    "umu.se": "Umeå universitet Familia",
    "svenskagravar.se": "SvenskaGravar",
    "gravar.se": "Gravar.se",
    "etjanster.stockholm.se": "Hitta graven Stockholm",
    "familjesidan.se": "Familjesidan",
    "minnessidor.fonus.se": "Fonus minnessidor",
    "tidningar.kb.se": "Kungliga biblioteket Svenska tidningar",
    "portrattarkiv.se": "Svenskt Porträttarkiv",
    "swedishportraits.com": "Svenskt Porträttarkiv",
    "digitaltmuseum.se": "DigitaltMuseum",
    "hembygd.se": "Sveriges Hembygdsförbund",
    "kringla.nu": "Kringla / Riksantikvarieämbetet",
    "alvin-portal.org": "Alvin",
    "runeberg.org": "Projekt Runeberg",
    "familysearch.org": "FamilySearch Swedish records",
    "wikitree.com": "WikiTree Sweden",
    "geneanet.org": "Geneanet Swedish public index",
}

SOURCE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "national-core",
        (
            "sok.riksarkivet.se",
            "riksarkivet.se",
            "slaktdata.org",
            "register.slaktdata.org",
            "rotter.se",
            "forum.rotter.se",
        ),
    ),
    (
        "military-regional",
        (
            "sokdatabas.soldatreg.se",
            "soldatreg.se",
            "blekingesf.se",
            "lanspumpen.se",
            "ep.liu.se",
            "stadsarkivet.stockholm",
            "sok.stadsarkivet.stockholm.se",
            "umu.se",
        ),
    ),
    (
        "graves-memorials",
        (
            "svenskagravar.se",
            "gravar.se",
            "etjanster.stockholm.se",
            "familjesidan.se",
            "minnessidor.fonus.se",
        ),
    ),
    (
        "newspapers-portraits",
        (
            "tidningar.kb.se",
            "portrattarkiv.se",
            "swedishportraits.com",
            "digitaltmuseum.se",
            "hembygd.se",
            "kringla.nu",
            "alvin-portal.org",
            "runeberg.org",
        ),
    ),
    (
        "swedish-records-global",
        (
            "familysearch.org",
            "wikitree.com",
            "geneanet.org",
        ),
    ),
)


def _clean(value: Any, limit: int = 360) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _read(url: str, timeout: int = 7) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml,application/xml,text/xml,*/*",
            "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.7",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def _canonical_url(value: Any) -> str:
    raw = str(value or "").strip()
    if raw.startswith("//"):
        raw = "https:" + raw
    return raw[:700]


def _source_label(url: str, fallback: str) -> str:
    try:
        host = (urllib.parse.urlsplit(url).hostname or "").casefold()
        if host.startswith("www."):
            host = host[4:]
    except Exception:
        return fallback
    best = ""
    label = ""
    for domain, candidate in SITE_LABELS.items():
        d = domain.casefold()
        if d.startswith("www."):
            d = d[4:]
        if host == d or host.endswith("." + d):
            if len(d) > len(best):
                best = d
                label = candidate
    return f"Sweden genealogy · {label}" if label else fallback


def _contains_term(item: dict[str, str], term: str) -> bool:
    needle = term.casefold().strip()
    hay = " ".join(item.get(k, "") for k in ("title", "url", "snippet")).casefold()
    return bool(needle and needle in hay)


def _parse_rss(payload: bytes, group: str, term: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(payload)
    except Exception:
        return []
    rows: list[dict[str, str]] = []
    fallback = f"Sweden genealogy source network · {group}"
    for node in root.findall(".//item"):
        url = _canonical_url(node.findtext("link"))
        row = {
            "index": _source_label(url, fallback),
            "title": _clean(node.findtext("title"), 180) or url,
            "url": url,
            "snippet": _clean(node.findtext("description"), 420),
            "date": _clean(node.findtext("pubDate"), 60),
        }
        if row["title"] and _contains_term(row, term):
            rows.append(row)
    return rows


def _query_group(term: str, group: str, domains: tuple[str, ...]) -> list[dict[str, str]]:
    sites = " OR ".join(f"site:{domain}" for domain in domains)
    query = f'"{term}" ({sites})'
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "rss",
            "count": 50,
            "first": 1,
            "mkt": "sv-SE",
            "setlang": "sv",
        }
    )
    return _parse_rss(_read("https://www.bing.com/search?" + params), group, term)

def riksarkivet_transcribed(term: str) -> list[dict[str, str]]:
    """Search Riksarkivet's official Search API for digitised transcribed records.

    This mirrors the public search surface's "Digitised material only" plus
    "Transcribed material only" mode. Results stay archival-record mentions;
    no nearby words are promoted into inferred people or family relationships.
    """
    params = urllib.parse.urlencode(
        {
            "transcribed_text": term,
            "only_digitised_materials": "true",
            "limit": 100,
            "offset": 0,
            "sort": "relevance",
        }
    )
    payload = _read("https://data.riksarkivet.se/api/records?" + params, timeout=8)
    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
    except Exception:
        return []

    rows: list[dict[str, str]] = []
    items = data.get("items", []) if isinstance(data, dict) else []
    for item in items[:100]:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata") or {}
        links = item.get("_links") or {}
        transcribed = item.get("transcribedText") or {}
        snippets = transcribed.get("snippets") or []

        snippet_parts = []
        for sn in snippets[:4]:
            if isinstance(sn, dict):
                text = _clean(sn.get("text"), 260)
                if text:
                    snippet_parts.append(text)

        hierarchy = metadata.get("hierarchy") or []
        hierarchy_caption = ""
        for node in hierarchy:
            if isinstance(node, dict) and node.get("caption"):
                hierarchy_caption = _clean(node.get("caption"), 160)
                break

        record_id = _clean(item.get("id"), 90)
        reference = _clean(metadata.get("referenceCode"), 120)
        title = (
            _clean(item.get("caption"), 180)
            or hierarchy_caption
            or reference
            or (f"Riksarkivet record {record_id}" if record_id else "Riksarkivet record")
        )
        url = _canonical_url(links.get("html"))
        if not url and record_id:
            url = f"https://sok.riksarkivet.se/arkiv/{urllib.parse.quote(record_id)}"
        context = " | ".join(
            x for x in (
                reference,
                _clean(metadata.get("date"), 60),
                _clean(metadata.get("note"), 180),
                " ".join(snippet_parts),
            )
            if x
        )
        row = {
            "index": "Sweden genealogy · Riksarkivet transcribed archives",
            "title": title,
            "url": url,
            "snippet": _clean(context, 420),
            "date": _clean(metadata.get("date"), 60),
        }
        if row["title"] and _contains_term(row, term):
            rows.append(row)
    return rows


def _group_adapter(index: int) -> Callable[[str], list[dict[str, str]]]:
    def run(term: str) -> list[dict[str, str]]:
        group, domains = SOURCE_GROUPS[index]
        return _query_group(term, group, domains)

    return run


ADAPTERS: tuple[Callable[[str], list[dict[str, str]]], ...] = (
    riksarkivet_transcribed,
) + tuple(_group_adapter(i) for i in range(len(SOURCE_GROUPS)))


def sweden_genealogy_mentions(term: str) -> dict[str, Any]:
    """Best-effort surname discovery across currently accessible Swedish sources.

    Results are literal public mentions, not inferred people or kinship. Paywalled
    databases are deliberately excluded. Sources that offer a free public search
    surface but optional paid extras remain eligible; V24 only records the public
    result URL and never attempts to cross a paywall or authenticated session.
    """
    term = str(term or "").strip()[:80]
    if not term:
        return {"source": SOURCE_NAME, "items": []}

    pool = ThreadPoolExecutor(max_workers=len(ADAPTERS), thread_name_prefix="things-se-genealogy")
    futures = {pool.submit(fn, term): fn for fn in ADAPTERS}
    pending = set(futures)
    collected: list[dict[str, str]] = []
    try:
        import time

        deadline = time.monotonic() + SEARCH_WINDOW_SECONDS
        while pending and len(collected) < MAX_ITEMS:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            done, pending = wait(pending, timeout=remaining, return_when=FIRST_COMPLETED)
            if not done:
                break
            for future in done:
                try:
                    collected.extend(future.result() or [])
                except Exception:
                    continue
    finally:
        for future in pending:
            future.cancel()
        pool.shutdown(wait=False, cancel_futures=True)

    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for item in collected:
        if not _contains_term(item, term):
            continue
        identity = (item.get("url") or "").casefold().strip() or (
            item.get("title", "").casefold().strip() + "|" + item.get("index", "").casefold().strip()
        )
        if not identity or identity in seen:
            continue
        seen.add(identity)
        out.append(item)
        if len(out) >= MAX_ITEMS:
            break

    return {"source": SOURCE_NAME, "items": out}
