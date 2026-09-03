#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
import urllib.parse
from typing import Any, Callable

import things_falcon_bridge_base as base
import things_falcon_bridge_v3 as v3

WT_APP_ID = "ThingsUniverseV24"
WT_ANCESTOR_DEPTH = 8
MAX_RELATIONS = 44


def _wt_params(**kwargs: Any) -> str:
    params = {"appId": WT_APP_ID, **kwargs}
    return urllib.parse.urlencode(params)


def _wt_display(person: dict[str, Any] | None) -> str:
    person = person or {}
    first = base.text_clean(person.get("RealName") or person.get("FirstName"), 50)
    middle = base.text_clean(person.get("MiddleName"), 45)
    last = base.text_clean(person.get("LastNameCurrent") or person.get("LastNameAtBirth"), 60)
    pieces = [x for x in (first, middle, last) if x]
    if pieces:
        return " ".join(pieces)
    raw = base.text_clean(person.get("Name"), 70)
    return re.sub(r"-\d+$", "", raw).replace("_", " ")


def _wt_people_dict(value: Any) -> dict[str, dict[str, Any]]:
    if isinstance(value, dict):
        return {str(k): v for k, v in value.items() if isinstance(v, dict)}
    if isinstance(value, list):
        return {str(v.get("Id") or i): v for i, v in enumerate(value) if isinstance(v, dict)}
    return {}


def _same_id(a: Any, b: Any) -> bool:
    if a in (None, "", 0) or b in (None, "", 0):
        return False
    return str(a) == str(b)


def wikitree_v4(term: str) -> dict[str, Any]:
    words = [x for x in re.split(r"\s+", term.strip()) if x]
    params: dict[str, Any] = {
        "action": "searchPerson",
        "limit": 12,
        "fields": "Id,Name,FirstName,MiddleName,RealName,LastNameAtBirth,LastNameCurrent,Gender,BirthDate,DeathDate,BirthLocation,DeathLocation,Father,Mother",
        "lastNameMatch": "all",
    }
    if len(words) >= 2:
        params["FirstName"] = words[0]
        params["LastName"] = words[-1]
    else:
        params["LastName"] = term.strip()
    data = base.get_json("https://api.wikitree.com/api.php?" + _wt_params(**params))
    payload = data[0] if isinstance(data, list) and data else data
    matches = payload.get("matches", []) if isinstance(payload, dict) else []
    rows = []
    for p in matches[:12]:
        if not isinstance(p, dict):
            continue
        rows.append({k: p.get(k) for k in (
            "Id", "Name", "FirstName", "MiddleName", "RealName", "LastNameAtBirth",
            "LastNameCurrent", "Gender", "BirthDate", "DeathDate", "BirthLocation",
            "DeathLocation", "Father", "Mother",
        ) if p.get(k) not in (None, "", 0)})
    return base.source("WikiTree", rows, 8)


base.GATHERERS = tuple(wikitree_v4 if fn.__name__ == "wikitree" else fn for fn in base.GATHERERS)
v3.MAX_RELATIONS = MAX_RELATIONS


def _wt_relatives(key: str) -> dict[str, Any]:
    if not key:
        return {}
    fields = "Id,Name,FirstName,MiddleName,RealName,LastNameAtBirth,LastNameCurrent,Gender,BirthDate,DeathDate,Father,Mother"
    data = base.get_json(
        "https://api.wikitree.com/api.php?" + _wt_params(
            action="getRelatives",
            keys=key,
            fields=fields,
            getParents=1,
            getChildren=1,
            getSiblings=1,
            getSpouses=1,
        ),
        timeout=10,
    )
    payload = data[0] if isinstance(data, list) and data else data
    items = payload.get("items", []) if isinstance(payload, dict) else []
    item = items[0] if items and isinstance(items[0], dict) else {}
    person = dict(item.get("person") or {})
    for field in ("Parents", "Children", "Siblings", "Spouses"):
        if field not in person and item.get(field):
            person[field] = item[field]
    return person


def _wt_ancestors(key: str, depth: int = WT_ANCESTOR_DEPTH) -> list[dict[str, Any]]:
    if not key:
        return []
    fields = "Id,Name,FirstName,MiddleName,RealName,LastNameAtBirth,LastNameCurrent,Gender,Father,Mother,BirthDate,DeathDate"
    data = base.get_json(
        "https://api.wikitree.com/api.php?" + _wt_params(
            action="getAncestors",
            key=key,
            depth=depth,
            fields=fields,
            resolveRedirect=1,
        ),
        timeout=14,
    )
    payload = data[0] if isinstance(data, list) and data else data
    ancestors = payload.get("ancestors", []) if isinstance(payload, dict) else []
    return [x for x in ancestors if isinstance(x, dict)]


def _family_row(subject: Any, label: Any, relation: str, confidence: float = 0.99) -> dict[str, Any] | None:
    a = base.text_clean(subject, 70)
    b = base.text_clean(label, 70)
    if not a or not b or a.casefold() == b.casefold():
        return None
    return {
        "subject": a,
        "label": b,
        "relation": relation,
        "confidence": confidence,
        "sources": ["WikiTree"],
        "kind": "family",
        "note": "",
    }


def _surname_row(label: Any, relation: str = "shares surname") -> dict[str, Any] | None:
    b = base.text_clean(label, 70)
    if not b:
        return None
    return {
        "label": b,
        "relation": relation,
        "confidence": 0.94,
        "sources": ["WikiTree"],
        "kind": "surname",
        "note": "",
    }


def _gendered(person: dict[str, Any], male: str, female: str, neutral: str) -> str:
    g = str(person.get("Gender") or "").casefold()
    if g == "male":
        return male
    if g == "female":
        return female
    return neutral


def _direct_family(person: dict[str, Any]) -> list[dict[str, Any]]:
    root = _wt_display(person)
    root_id = person.get("Id")
    out: list[dict[str, Any]] = []

    for p in _wt_people_dict(person.get("Parents")).values():
        relation = "parent of"
        if _same_id(p.get("Id"), person.get("Father")):
            relation = "father of"
        elif _same_id(p.get("Id"), person.get("Mother")):
            relation = "mother of"
        row = _family_row(_wt_display(p), root, relation)
        if row:
            out.append(row)

    for child in _wt_people_dict(person.get("Children")).values():
        relation = "parent of"
        if _same_id(root_id, child.get("Father")):
            relation = "father of"
        elif _same_id(root_id, child.get("Mother")):
            relation = "mother of"
        row = _family_row(root, _wt_display(child), relation)
        if row:
            out.append(row)

    for sibling in _wt_people_dict(person.get("Siblings")).values():
        row = _family_row(root, _wt_display(sibling), "sibling of")
        if row:
            out.append(row)

    for spouse in _wt_people_dict(person.get("Spouses")).values():
        row = _family_row(root, _wt_display(spouse), "spouse of")
        if row:
            out.append(row)

    return out


def _ancestor_relation(person: dict[str, Any], generation: int) -> str:
    base_name = _gendered(person, "grandfather", "grandmother", "grandparent")
    greats = max(0, generation - 2)
    if greats <= 0:
        return base_name + " of"
    if greats <= 4:
        return ("great-" * greats) + base_name + " of"
    return f"{greats}× great-{base_name} of"


def _unique_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        subject = str(row.get("subject") or "").casefold()
        label = str(row.get("label") or "").casefold()
        relation = str(row.get("relation") or "").casefold()
        key = (subject, label, relation)
        if not label or not relation or key in seen:
            continue
        seen.add(key)
        out.append(row)
        if len(out) >= MAX_RELATIONS:
            break
    return out


def _exact_wikitree_match(term: str, items: list[dict[str, Any]]) -> dict[str, Any] | None:
    wanted = re.sub(r"\s+", " ", term.strip()).casefold()
    exact = [p for p in items if _wt_display(p).casefold() == wanted]
    return exact[0] if len(exact) == 1 else None


def family_relations(
    term: str,
    evidence: list[dict[str, Any]],
    emit: Callable[[list[dict[str, Any]]], None] | None = None,
) -> list[dict[str, Any]]:
    block = next((x for x in evidence if x.get("source") == "WikiTree"), None)
    items = [x for x in (block or {}).get("items", []) if isinstance(x, dict)]
    if not items:
        return []

    rows: list[dict[str, Any]] = []
    one_word = len([x for x in term.strip().split() if x]) == 1

    for item in items[:6 if one_word else 2]:
        display = _wt_display(item)
        if one_word and display:
            sr = _surname_row(display)
            if sr:
                rows.append(sr)
        profile = _wt_relatives(str(item.get("Name") or ""))
        if profile:
            rows.extend(_direct_family(profile))
            rows = _unique_rows(rows)
            if emit:
                emit(rows)
        if len(rows) >= MAX_RELATIONS:
            return rows[:MAX_RELATIONS]

    root_item = None if one_word else _exact_wikitree_match(term, items)
    if not root_item:
        return _unique_rows(rows)

    root_key = str(root_item.get("Name") or "")
    root_profile = _wt_relatives(root_key) or root_item
    root_name = _wt_display(root_profile) or _wt_display(root_item)

    parents = list(_wt_people_dict(root_profile.get("Parents")).values())
    for parent in parents[:2]:
        parent_rel = _wt_relatives(str(parent.get("Name") or ""))
        for aunt_uncle in list(_wt_people_dict(parent_rel.get("Siblings")).values())[:6]:
            au_name = _wt_display(aunt_uncle)
            relation = _gendered(aunt_uncle, "uncle of", "aunt of", "parent's sibling of")
            row = _family_row(au_name, root_name, relation)
            if row:
                rows.append(row)
            au_rel = _wt_relatives(str(aunt_uncle.get("Name") or ""))
            for cousin in list(_wt_people_dict(au_rel.get("Children")).values())[:6]:
                row = _family_row(root_name, _wt_display(cousin), "first cousin of")
                if row:
                    rows.append(row)
            for spouse in list(_wt_people_dict(au_rel.get("Spouses")).values())[:2]:
                relation = _gendered(spouse, "uncle by marriage of", "aunt by marriage of", "relative by marriage of")
                row = _family_row(_wt_display(spouse), root_name, relation)
                if row:
                    rows.append(row)
            rows = _unique_rows(rows)
            if emit:
                emit(rows)
            if len(rows) >= MAX_RELATIONS:
                return rows[:MAX_RELATIONS]

    for spouse in list(_wt_people_dict(root_profile.get("Spouses")).values())[:2]:
        sp_rel = _wt_relatives(str(spouse.get("Name") or ""))
        for p in list(_wt_people_dict(sp_rel.get("Parents")).values())[:2]:
            relation = _gendered(p, "father-in-law of", "mother-in-law of", "parent-in-law of")
            row = _family_row(_wt_display(p), root_name, relation)
            if row:
                rows.append(row)
        for sib in list(_wt_people_dict(sp_rel.get("Siblings")).values())[:6]:
            row = _family_row(_wt_display(sib), root_name, "sibling-in-law of")
            if row:
                rows.append(row)

    for sibling in list(_wt_people_dict(root_profile.get("Siblings")).values())[:6]:
        sib_rel = _wt_relatives(str(sibling.get("Name") or ""))
        for spouse in list(_wt_people_dict(sib_rel.get("Spouses")).values())[:2]:
            row = _family_row(_wt_display(spouse), root_name, "sibling-in-law of")
            if row:
                rows.append(row)

    rows = _unique_rows(rows)
    if emit:
        emit(rows)

    ancestors = _wt_ancestors(root_key, WT_ANCESTOR_DEPTH)
    by_id = {str(p.get("Id")): p for p in ancestors if p.get("Id") not in (None, "", 0)}
    root_id = str(root_item.get("Id") or root_profile.get("Id") or "")
    if root_id and root_id in by_id:
        generations: dict[str, int] = {root_id: 0}
        queue = [root_id]
        while queue:
            pid = queue.pop(0)
            person = by_id.get(pid) or {}
            gen = generations[pid]
            for parent_id in (person.get("Father"), person.get("Mother")):
                sid = str(parent_id or "")
                if sid and sid in by_id and sid not in generations:
                    generations[sid] = gen + 1
                    queue.append(sid)

        grouped: dict[int, list[dict[str, Any]]] = {}
        for pid, gen in generations.items():
            if gen >= 2 and pid in by_id:
                grouped.setdefault(gen, []).append(by_id[pid])

        for gen in sorted(grouped):
            for anc in grouped[gen][:4]:
                row = _family_row(_wt_display(anc), root_name, _ancestor_relation(anc, gen))
                if row:
                    rows.append(row)
            rows = _unique_rows(rows)
            if emit:
                emit(rows)
            if len(rows) >= MAX_RELATIONS:
                break

    return _unique_rows(rows)


def merge_relations(*groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for group in groups:
        for row in group:
            key = (
                str(row.get("subject") or "").casefold(),
                str(row.get("label") or "").casefold(),
                str(row.get("relation") or "").casefold(),
            )
            if not key[1] or not key[2] or key in seen:
                continue
            seen.add(key)
            out.append(row)
            if len(out) >= MAX_RELATIONS:
                return out
    return out


def enrich_v4(
    term: str,
    context: list[str] | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    evidence = v3.gather_parallel(term)
    compact = base.compact_evidence(evidence, budget=3600)
    allowed_sources = {str(item.get("source")) for item in compact if item.get("source")}

    basic = v3.direct_relations(term, compact)
    for row in basic:
        row.setdefault("kind", "surname" if "surname" in str(row.get("relation") or "").casefold() else "other")

    def send(phase: str, relations: list[dict[str, Any]], engine: str) -> None:
        if not progress_callback:
            return
        progress_callback({
            "term": term,
            "relations": relations[:MAX_RELATIONS],
            "evidence_sources": sorted(allowed_sources),
            "engine": engine,
            "phase": phase,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        })

    send("evidence", basic, "multi-source evidence; family walk + Falcon pending")

    family: list[dict[str, Any]] = []
    if "WikiTree" in allowed_sources:
        family = family_relations(
            term,
            compact,
            emit=lambda rows: send(
                "family",
                merge_relations(basic, rows),
                "multi-source evidence + explicit WikiTree kinship; Falcon pending",
            ),
        )

    if not compact:
        return {
            "term": term,
            "relations": merge_relations(basic, family),
            "evidence_sources": sorted(allowed_sources),
            "engine": "multi-source evidence",
            "phase": "done",
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }

    prompt = {
        "term": term,
        "context": (context or [])[:6],
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
        inferred = v3.parse_tsv(answer, term, allowed_sources)
    except Exception as exc:
        print(f"Things Falcon synthesis deferred for {term}: {type(exc).__name__}: {exc}", flush=True)
        inferred = []

    relations = merge_relations(basic, family, inferred)
    return {
        "term": term,
        "relations": relations,
        "evidence_sources": sorted(allowed_sources),
        "engine": "Falcon3-10B-Instruct-1.58bit via BitNet + multi-source evidence + explicit kinship rules",
        "phase": "done",
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }


v3.enrich = enrich_v4

if __name__ == "__main__":
    raise SystemExit(v3.main())
