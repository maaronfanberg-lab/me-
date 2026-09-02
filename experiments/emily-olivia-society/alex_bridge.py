#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

ALEX_ID = 3
ALEX_NAME = "Alex"
REPOSITORY = "maaronfanberg-lab/me-"
ISSUE_NUMBER = 277
ALEX_GITHUB_LOGIN = "maaronfanberg-lab"
MAX_ALEX_TURN_CHARS = 700
_API_ROOT = f"https://api.github.com/repos/{REPOSITORY}"
_ACK_PATTERN = re.compile(r"<!--\s*alex-ack:(\d+)\s*-->", re.IGNORECASE)


@dataclass(frozen=True)
class AlexParticipant:
    agent_id: int = ALEX_ID
    name: str = ALEX_NAME


def _parse_target(body: str) -> tuple[str, str]:
    text = str(body or "").strip()
    for prefix, target in (("@Emily", "Emily"), ("@Olivia", "Olivia")):
        if text.lower().startswith(prefix.lower()):
            cleaned = text[len(prefix):].lstrip(" :,.-\n\t")
            return target, cleaned
    return "both", text


class AlexBridgeClient:
    """Treat comments on one dedicated GitHub issue as human Alex turns.

    Only comments authored by the repository owner are accepted as Alex. A
    successful Stanford-generated reply is posted back into the issue with a
    hidden acknowledgement marker, which makes queue consumption durable across
    runner handoffs and crashes without another deployment service.
    """

    def __init__(self) -> None:
        self.token = str(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or "").strip()
        self.enabled = bool(self.token)

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict | None = None,
    ) -> object:
        if not self.enabled:
            raise RuntimeError("Alex GitHub doorway is unavailable without GH_TOKEN/GITHUB_TOKEN.")
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            _API_ROOT + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "emily-olivia-community-runner",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
            raise RuntimeError(f"Alex GitHub doorway HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Alex GitHub doorway request failed: {exc}") from exc

    def _comments(self) -> list[dict]:
        if not self.enabled:
            return []
        payload = self._request(
            f"/issues/{ISSUE_NUMBER}/comments?per_page=100&sort=created&direction=asc"
        )
        if not isinstance(payload, list):
            raise RuntimeError("Alex GitHub doorway comments response is malformed.")
        return [row for row in payload if isinstance(row, dict)]

    def pending(self) -> list[dict]:
        comments = self._comments()
        acknowledged: set[str] = set()
        for row in comments:
            for match in _ACK_PATTERN.finditer(str(row.get("body", ""))):
                acknowledged.add(match.group(1))

        clean: list[dict] = []
        for row in comments:
            author = str((row.get("user") or {}).get("login", ""))
            row_id = str(row.get("id", "")).strip()
            if author != ALEX_GITHUB_LOGIN or not row_id or row_id in acknowledged:
                continue
            target, text = _parse_target(str(row.get("body", "")))
            if not text or len(text) > MAX_ALEX_TURN_CHARS:
                continue
            clean.append(
                {
                    "id": row_id,
                    "speaker": ALEX_NAME,
                    "text": text,
                    "target": target,
                    "at": str(row.get("created_at", "")).strip(),
                    "source_url": str(row.get("html_url", "")).strip(),
                }
            )
        return clean

    def first_for(self, agent_name: str) -> dict | None:
        wanted = str(agent_name or "").strip()
        for row in self.pending():
            if row["target"] in {"both", wanted}:
                return row
        return None

    def ack(self, queue_id: str, speaker: str, reply: str) -> dict:
        row_id = str(queue_id or "").strip()
        who = str(speaker or "").strip()
        text = str(reply or "").strip()
        if not row_id or not who or not text or not self.enabled:
            return {"acknowledged": 0}
        body = f"**{who}:** {text}\n\n<!-- alex-ack:{row_id} -->"
        payload = self._request(
            f"/issues/{ISSUE_NUMBER}/comments",
            method="POST",
            body={"body": body},
        )
        comment_id = payload.get("id") if isinstance(payload, dict) else None
        return {
            "acknowledged": 1 if comment_id else 0,
            "comment_id": comment_id,
            "url": payload.get("html_url") if isinstance(payload, dict) else None,
        }
