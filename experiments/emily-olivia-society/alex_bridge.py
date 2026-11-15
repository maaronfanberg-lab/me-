#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone

ALEX_ID = 3
ALEX_NAME = "Alex"
MAX_ALEX_TURN_CHARS = 700
NTFY_ROOT = "https://ntfy.sh"
DEFAULT_ALEX_TOPIC = "eo-alex-4f542bcc00c9cacc4517cc7c99c99ffe"
_ALEX_TITLE = "Alex"
_ACK_TITLE = "AlexAck"


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


def _has_semantic_payload(text: str) -> bool:
    """Ignore transport/test punctuation without rejecting emoji-only Alex turns."""
    value = str(text or "").strip()
    if not value:
        return False
    if re.search(r"\w", value, flags=re.UNICODE):
        return True
    return any(ord(char) > 127 and not char.isspace() for char in value)


def _iso_time(value: object) -> str:
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError, OverflowError):
        return datetime.now(timezone.utc).isoformat()


class AlexBridgeClient:
    """Use a tiny ntfy topic as Alex's browser-to-runner mailbox.

    The topic is transport only. Emily and Olivia still process Alex through the
    same Stanford observe -> remember -> retrieve -> reflect -> plan/react -> act
    chain. Mailbox outages never terminate their autonomous Community run.

    Consumed message ids are acknowledged back onto the same topic. A local ack
    backlog prevents a transient ntfy write failure from replaying the same Alex
    turn repeatedly during the current runner session; later polls retry the ack.
    """

    def __init__(self) -> None:
        self.topic = str(os.environ.get("COMMUNITY_ALEX_NTFY_TOPIC") or DEFAULT_ALEX_TOPIC).strip()
        self.enabled = bool(self.topic)
        self._locally_acked: set[str] = set()
        self._ack_backlog: set[str] = set()

    @property
    def topic_url(self) -> str:
        quoted = urllib.parse.quote(self.topic, safe="")
        return f"{NTFY_ROOT}/{quoted}"

    def _request(self, request: urllib.request.Request) -> bytes:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=12) as response:
                    return response.read()
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")[:800]
                last_error = RuntimeError(f"Alex mailbox HTTP {exc.code}: {detail}")
                if exc.code < 500 and exc.code != 429:
                    break
            except urllib.error.URLError as exc:
                last_error = RuntimeError(f"Alex mailbox request failed: {exc}")
            if attempt < 2:
                time.sleep(0.5 * (2**attempt))
        if isinstance(last_error, RuntimeError):
            raise last_error
        raise RuntimeError("Alex mailbox request failed.")

    def _poll_rows(self) -> list[dict]:
        if not self.enabled:
            return []
        url = f"{self.topic_url}/json?poll=1&since=all"
        request = urllib.request.Request(
            url,
            method="GET",
            headers={"Accept": "application/x-ndjson", "User-Agent": "emily-olivia-community-runner"},
        )
        raw = self._request(request).decode("utf-8", errors="replace")
        rows: list[dict] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and row.get("event") == "message":
                rows.append(row)
        return rows

    def _publish(self, message: str, *, title: str) -> dict:
        if not self.enabled:
            raise RuntimeError("Alex direct room mailbox is not configured.")
        request = urllib.request.Request(
            self.topic_url,
            data=str(message).encode("utf-8"),
            method="POST",
            headers={
                "Title": title,
                "Content-Type": "text/plain; charset=utf-8",
                "User-Agent": "emily-olivia-community-runner",
            },
        )
        raw = self._request(request).decode("utf-8", errors="replace")
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            raise RuntimeError("Alex mailbox publish returned malformed JSON.")
        return payload

    def _flush_ack_backlog(self) -> None:
        for row_id in list(self._ack_backlog):
            try:
                payload = self._publish(row_id, title=_ACK_TITLE)
            except Exception as exc:
                print(f"WARNING: Alex mailbox ack retry deferred for {row_id}: {exc}", file=sys.stderr, flush=True)
                continue
            if str(payload.get("id", "")).strip():
                self._ack_backlog.discard(row_id)

    def pending(self) -> list[dict]:
        if not self.enabled:
            return []
        self._flush_ack_backlog()
        try:
            rows = self._poll_rows()
        except Exception as exc:
            print(f"WARNING: Alex mailbox poll unavailable; Emily and Olivia continue autonomously: {exc}", file=sys.stderr, flush=True)
            return []

        acknowledged = {
            str(row.get("message", "")).strip()
            for row in rows
            if str(row.get("title", "")).strip() == _ACK_TITLE
            and str(row.get("message", "")).strip()
        }
        acknowledged.update(self._locally_acked)

        clean: list[dict] = []
        for row in rows:
            if str(row.get("title", "")).strip() != _ALEX_TITLE:
                continue
            row_id = str(row.get("id", "")).strip()
            if not row_id or row_id in acknowledged:
                continue
            target, text = _parse_target(str(row.get("message", "")))
            if not text or len(text) > MAX_ALEX_TURN_CHARS or not _has_semantic_payload(text):
                continue
            clean.append(
                {
                    "id": row_id,
                    "speaker": ALEX_NAME,
                    "text": text,
                    "target": target,
                    "at": _iso_time(row.get("time")),
                    "source_url": self.topic_url,
                }
            )
        return clean

    def first_for(self, agent_name: str) -> dict | None:
        wanted = str(agent_name or "").strip()
        for row in self.pending():
            if row["target"] in {"both", wanted}:
                return row
        return None

    def ack(self, ids: list[str]) -> dict:
        clean = [str(value).strip() for value in ids if str(value).strip()]
        if not clean or not self.enabled:
            return {"acknowledged": 0}

        acknowledged = 0
        for row_id in clean:
            self._locally_acked.add(row_id)
            try:
                payload = self._publish(row_id, title=_ACK_TITLE)
            except Exception as exc:
                self._ack_backlog.add(row_id)
                print(f"WARNING: Alex mailbox ack queued locally for {row_id}: {exc}", file=sys.stderr, flush=True)
                acknowledged += 1
                continue
            if str(payload.get("id", "")).strip():
                acknowledged += 1
            else:
                self._ack_backlog.add(row_id)
                acknowledged += 1
        return {"acknowledged": acknowledged}
