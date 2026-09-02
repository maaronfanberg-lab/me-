#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

ALEX_ID = 3
ALEX_NAME = "Alex"
DEFAULT_BRIDGE_URL = "https://emily-olivia-community.dfp6k69dw5.workers.dev"
OIDC_AUDIENCE = "emily-olivia-community"
MAX_ALEX_TURN_CHARS = 700
_VALID_TARGETS = {"Emily", "Olivia", "both"}


@dataclass(frozen=True)
class AlexParticipant:
    agent_id: int = ALEX_ID
    name: str = ALEX_NAME


class AlexBridgeClient:
    """Read and acknowledge private Alex turns through the Community worker.

    The GitHub runner authenticates with its short-lived Actions OIDC token.
    Local/smoke environments without Actions OIDC simply expose an empty queue.
    """

    def __init__(self) -> None:
        self.base_url = str(
            os.environ.get("COMMUNITY_ALEX_BRIDGE_URL", DEFAULT_BRIDGE_URL)
        ).strip().rstrip("/")
        self.request_url = str(os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL", "")).strip()
        self.request_token = str(os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "")).strip()
        self.enabled = bool(self.base_url and self.request_url and self.request_token)
        self._token = ""
        self._token_at = 0.0

    def _oidc_token(self) -> str:
        now = time.monotonic()
        if self._token and now - self._token_at < 120:
            return self._token
        if not self.enabled:
            raise RuntimeError("Alex bridge is unavailable outside an authorized GitHub Actions run.")
        separator = "&" if "?" in self.request_url else "?"
        url = self.request_url + separator + urllib.parse.urlencode({"audience": OIDC_AUDIENCE})
        request = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {self.request_token}",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"GitHub Actions OIDC token request failed: {exc}") from exc
        token = str(payload.get("value", "")).strip() if isinstance(payload, dict) else ""
        if not token:
            raise RuntimeError("GitHub Actions OIDC response did not contain a token.")
        self._token = token
        self._token_at = now
        return token

    def _request(self, path: str, *, method: str = "GET", body: dict | None = None) -> dict:
        token = self._oidc_token()
        data = None if body is None else json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "emily-olivia-community-runner",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            if exc.code == 401:
                self._token = ""
                self._token_at = 0.0
            raise RuntimeError(f"Alex bridge HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Alex bridge request failed: {exc}") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Alex bridge returned a non-object response.")
        return payload

    def pending(self) -> list[dict]:
        if not self.enabled:
            return []
        payload = self._request("/api/alex/pending")
        rows = payload.get("messages", [])
        if not isinstance(rows, list):
            raise RuntimeError("Alex bridge pending response is malformed.")
        clean: list[dict] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            text = str(row.get("text", "")).strip()
            target = str(row.get("target", "both")).strip()
            row_id = str(row.get("id", "")).strip()
            if (
                not row_id
                or not text
                or len(text) > MAX_ALEX_TURN_CHARS
                or target not in _VALID_TARGETS
            ):
                continue
            clean.append(
                {
                    "id": row_id,
                    "speaker": ALEX_NAME,
                    "text": text,
                    "target": target,
                    "at": str(row.get("at", "")).strip(),
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
        return self._request("/api/alex/ack", method="POST", body={"ids": clean})
