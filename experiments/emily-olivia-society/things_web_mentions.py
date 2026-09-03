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
        if row and _contains_term(row, term):
            rows.append(row)
    return rows


def _bing_query(term: str, query: str, first: int = 1) -> list[dict[str, str]]:
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
    return _parse_rss(payload, "Bing web", term)


def bing_exact_page1(term: str) -> list[dict[str, str]]:
    return _bing_query(term, f'"{term}"', 1)


def bing_exact_page2(term: str) -> list[dict[str, str]]:
    return _bing_query(term, f'"{term}"', 51)


def bing_exact_page3(term: str) -> list[dict[str, str]]:
    return _bing_query(term, f'"{term}"', 101)


def bing_un(term: str) -> list[dict[str, str]]:
    return _bing_query(term, f'"{term}" (site:un.org OR site:digitallibrary.un.org)', 1)


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
    concept lookup.
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
