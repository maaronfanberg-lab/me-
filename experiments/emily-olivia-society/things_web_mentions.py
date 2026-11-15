#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Callable

USER_AGENT = "Things-Universe-v24/1.0 (public web mention discovery)"
SOURCE_NAME = "Web-wide mentions"
MAX_ITEMS = 220
SEARCH_WINDOW_SECONDS = 10.0

# UNPAN is a network, not one authoritative upstream database. Its public
# resources are contributed by UN DESA/DPIDG and current UNPAN member
# institutions. Search those original public domains directly so V24 can cite
# the originating institution rather than treating the UNPAN portal itself as
# the evidence source.
UNPAN_SITE_LABELS: dict[str, str] = {
    "publicadministration.desa.un.org": "UN DESA/DPIDG",
    "un.org": "United Nations",
    "digitallibrary.un.org": "UN Digital Library",
    "documents.un.org": "UN Official Documents",
    "uneca.org": "UN ECA",
    "unidep.org": "IDEP",
    "ofpa.net": "OFPA",
    "uclga.org": "UCLG Africa",
    "aapam.org": "AAPAM",
    "cafrad.org": "CAFRAD",
    "aapa.asia": "AAPA",
    "cgg.gov.in": "Centre for Good Governance",
    "eropa.co": "EROPA",
    "unescap.org": "UN ESCAP",
    "sass.org.cn": "RCOCI / SASS",
    "kipa.re.kr": "KIPA",
    "snu.ac.kr": "Seoul National University",
    "southasianetwork.org": "SANPA",
    "weforum.org": "World Economic Forum",
    "iis.ru": "Institute of Information Society",
    "nispa.sk": "NISPAcee",
    "respaweb.eu": "ReSPA",
    "arado.org": "ARADO",
    "mbrsg.ae": "Mohammed Bin Rashid School of Government",
    "escwa.un.org": "UN ESCWA",
    "aspanet.org": "ASPA",
    "caricad.net": "CARICAD",
    "clad.org": "CLAD",
    "eclac.org": "UN ECLAC",
    "icap.ac.cr": "ICAP",
    "inap.mx": "INAP Mexico",
    "ipac.ca": "IPAC/IAPC",
    "ipma-hr.org": "IPMA-HR",
    "ciiiap.org.br": "CIIIAP",
    "iias-iisa.org": "IIAS",
    "we-gov.org": "WeGO",
    "povertyactionlab.org": "J-PAL",
}

UNPAN_SOURCE_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "UN official",
        (
            "publicadministration.desa.un.org",
            "un.org",
            "digitallibrary.un.org",
            "documents.un.org",
        ),
    ),
    (
        "Africa",
        ("uneca.org", "unidep.org", "ofpa.net", "uclga.org", "aapam.org", "cafrad.org"),
    ),
    (
        "Asia-Pacific",
        (
            "aapa.asia",
            "cgg.gov.in",
            "eropa.co",
            "unescap.org",
            "sass.org.cn",
            "kipa.re.kr",
            "snu.ac.kr",
            "southasianetwork.org",
        ),
    ),
    (
        "Europe-Middle East",
        (
            "weforum.org",
            "iis.ru",
            "nispa.sk",
            "respaweb.eu",
            "arado.org",
            "mbrsg.ae",
            "escwa.un.org",
        ),
    ),
    (
        "Americas-Global",
        (
            "aspanet.org",
            "caricad.net",
            "clad.org",
            "eclac.org",
            "icap.ac.cr",
            "inap.mx",
            "ipac.ca",
            "ipma-hr.org",
            "ciiiap.org.br",
            "iias-iisa.org",
            "we-gov.org",
            "povertyactionlab.org",
            "southasianetwork.org",
        ),
    ),
)


def _clean(value: Any, limit: int = 320) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _read(url: str, timeout: int = 7, accept: str = "*/*") -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def _canonical_url(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.startswith("//"):
        raw = "https:" + raw
    try:
        parsed = urllib.parse.urlsplit(raw)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            q = urllib.parse.parse_qs(parsed.query)
            raw = (q.get("uddg") or [raw])[0]
    except Exception:
        pass
    return raw[:700]


def _unpan_source_index(url: str, fallback: str) -> str:
    try:
        host = (urllib.parse.urlsplit(url).hostname or "").casefold().lstrip("www.")
    except Exception:
        return fallback
    best_domain = ""
    best_label = ""
    for domain, label in UNPAN_SITE_LABELS.items():
        d = domain.casefold().lstrip("www.")
        if host == d or host.endswith("." + d):
            if len(d) > len(best_domain):
                best_domain = d
                best_label = label
    return f"UNPAN source · {best_label}" if best_label else fallback


def _row(index: str, title: Any, url: Any, snippet: Any = "", date: Any = "") -> dict[str, str] | None:
    title_text = _clean(title, 180)
    url_text = _canonical_url(url)
    snippet_text = _clean(snippet, 420)
    if not title_text and not url_text:
        return None
    return {
        "index": _clean(index, 50),
        "title": title_text or url_text,
        "url": url_text,
        "snippet": snippet_text,
        "date": _clean(date, 60),
    }


def _contains_term(item: dict[str, Any], term: str) -> bool:
    needle = term.casefold().strip()
    if not needle:
        return False
    hay = " ".join(str(item.get(k) or "") for k in ("title", "url", "snippet")).casefold()
    return needle in hay


def _parse_rss(payload: bytes, index: str, term: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    try:
        root = ET.fromstring(payload)
    except Exception:
        return rows
    for item in root.findall(".//item"):
        row = _row(
            index,
            item.findtext("title"),
            item.findtext("link"),
            item.findtext("description"),
            item.findtext("pubDate"),
        )
        if row and index.startswith("UNPAN source network"):
            row["index"] = _unpan_source_index(row.get("url") or "", index)
        if row and _contains_term(row, term):
            rows.append(row)
    return rows


def _bing_query(term: str, query: str, first: int = 1, index: str = "Bing web") -> list[dict[str, str]]:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "rss",
            "count": 50,
            "first": first,
            "mkt": "en-US",
        }
    )
    payload = _read("https://www.bing.com/search?" + params, accept="application/rss+xml,application/xml,text/xml,*/*")
    return _parse_rss(payload, index, term)


def bing_exact_page1(term: str) -> list[dict[str, str]]:
    return _bing_query(term, f'"{term}"', 1)


def bing_exact_page2(term: str) -> list[dict[str, str]]:
    return _bing_query(term, f'"{term}"', 51)


def bing_exact_page3(term: str) -> list[dict[str, str]]:
    return _bing_query(term, f'"{term}"', 101)


def bing_un(term: str) -> list[dict[str, str]]:
    return _bing_query(term, f'"{term}" (site:un.org OR site:digitallibrary.un.org)', 1)


def _bing_unpan_group(term: str, group: str, domains: tuple[str, ...]) -> list[dict[str, str]]:
    sites = " OR ".join(f"site:{domain}" for domain in domains)
    return _bing_query(term, f'"{term}" ({sites})', 1, f"UNPAN source network · {group}")


def bing_unpan_official(term: str) -> list[dict[str, str]]:
    group, domains = UNPAN_SOURCE_GROUPS[0]
    return _bing_unpan_group(term, group, domains)


def bing_unpan_africa(term: str) -> list[dict[str, str]]:
    group, domains = UNPAN_SOURCE_GROUPS[1]
    return _bing_unpan_group(term, group, domains)


def bing_unpan_asia_pacific(term: str) -> list[dict[str, str]]:
    group, domains = UNPAN_SOURCE_GROUPS[2]
    return _bing_unpan_group(term, group, domains)


def bing_unpan_europe_middle_east(term: str) -> list[dict[str, str]]:
    group, domains = UNPAN_SOURCE_GROUPS[3]
    return _bing_unpan_group(term, group, domains)


def bing_unpan_americas_global(term: str) -> list[dict[str, str]]:
    group, domains = UNPAN_SOURCE_GROUPS[4]
    return _bing_unpan_group(term, group, domains)


def bing_genealogy(term: str) -> list[dict[str, str]]:
    return _bing_query(
        term,
        f'"{term}" (genealogy OR obituary OR census OR family OR ancestry OR memorial)',
        1,
    )


def google_news(term: str) -> list[dict[str, str]]:
    params = urllib.parse.urlencode(
        {
            "q": f'"{term}"',
            "hl": "en-US",
            "gl": "US",
            "ceid": "US:en",
        }
    )
    payload = _read(
        "https://news.google.com/rss/search?" + params,
        accept="application/rss+xml,application/xml,text/xml,*/*",
    )
    return _parse_rss(payload, "Google News", term)


def gdelt(term: str) -> list[dict[str, str]]:
    params = urllib.parse.urlencode(
        {
            "query": f'"{term}"',
            "mode": "ArtList",
            "maxrecords": 250,
            "format": "json",
            "sort": "HybridRel",
        }
    )
    payload = _read(
        "https://api.gdeltproject.org/api/v2/doc/doc?" + params,
        accept="application/json,*/*",
    )
    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
    except Exception:
        return []
    rows: list[dict[str, str]] = []
    for article in data.get("articles", []) if isinstance(data, dict) else []:
        row = _row(
            "GDELT",
            article.get("title"),
            article.get("url"),
            " ".join(
                str(article.get(k) or "")
                for k in ("domain", "language", "sourcecountry")
                if article.get(k)
            ),
            article.get("seendate"),
        )
        if row and _contains_term(row, term):
            rows.append(row)
    return rows


def internet_archive(term: str) -> list[dict[str, str]]:
    params = urllib.parse.urlencode(
        {
            "q": f'"{term}"',
            "fl[]": ["identifier", "title", "description", "creator", "date"],
            "rows": 100,
            "page": 1,
            "output": "json",
        },
        doseq=True,
    )
    payload = _read("https://archive.org/advancedsearch.php?" + params, accept="application/json,*/*")
    try:
        data = json.loads(payload.decode("utf-8", errors="replace"))
    except Exception:
        return []
    rows: list[dict[str, str]] = []
    docs = ((data.get("response") or {}).get("docs") or []) if isinstance(data, dict) else []
    for doc in docs:
        identifier = str(doc.get("identifier") or "").strip()
        creator = doc.get("creator")
        if isinstance(creator, list):
            creator = "; ".join(str(x) for x in creator[:5])
        description = doc.get("description")
        if isinstance(description, list):
            description = " ".join(str(x) for x in description[:3])
        row = _row(
            "Internet Archive",
            doc.get("title") or identifier,
            f"https://archive.org/details/{urllib.parse.quote(identifier)}" if identifier else "",
            " | ".join(x for x in (_clean(creator, 180), _clean(description, 260)) if x),
            doc.get("date"),
        )
        if row and _contains_term(row, term):
            rows.append(row)
    return rows


ADAPTERS: tuple[Callable[[str], list[dict[str, str]]], ...] = (
    bing_exact_page1,
    bing_exact_page2,
    bing_exact_page3,
    bing_un,
    bing_unpan_official,
    bing_unpan_africa,
    bing_unpan_asia_pacific,
    bing_unpan_europe_middle_east,
    bing_unpan_americas_global,
    bing_genealogy,
    google_news,
    gdelt,
    internet_archive,
)


def webwide_mentions(term: str) -> dict[str, Any]:
    """Search several independent public indexes for literal mentions of a term.

    This is deliberately best-effort. No finite set of public indexes can guarantee
    every page on the Internet, but results from each live index are merged and
    deduplicated so a rare surname can be swept much more deeply than a normal
    concept lookup. UNPAN-derived searches target the original UNPAN member and
    UN institutional domains, preserving the originating institution in the result.
    """
    term = str(term or "").strip()[:80]
    if not term:
        return {"source": SOURCE_NAME, "items": []}

    pool = ThreadPoolExecutor(max_workers=len(ADAPTERS), thread_name_prefix="things-web")
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
            (item.get("title") or "").casefold().strip()
            + "|"
            + (item.get("index") or "").casefold().strip()
        )
        if not identity or identity in seen:
            continue
        seen.add(identity)
        out.append(item)
        if len(out) >= MAX_ITEMS:
            break

    return {"source": SOURCE_NAME, "items": out}
