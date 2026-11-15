#!/usr/bin/env python3
"""Remote MCP entrypoint for Claude custom connectors.

This exposes the same Alex Repo Simulator tools over Streamable HTTP at /mcp.
It is intentionally stateless at the transport layer so it can run behind a
normal HTTPS host or serverless platform.
"""

from __future__ import annotations

import os

# Hosted filesystems are often read-only. Keep transient run history in /tmp.
os.environ.setdefault("SIMULATOR_RUN_DIR", "/tmp/alex-repo-simulator-runs")

from mcp_server import mcp

_mcp_app = mcp.streamable_http_app(
    host="0.0.0.0",
    stateless_http=True,
    json_response=True,
)


async def app(scope, receive, send):
    """ASGI wrapper that adds a normal GET health endpoint beside MCP."""
    if (
        scope.get("type") == "http"
        and scope.get("method") == "GET"
        and scope.get("path") == "/health"
    ):
        body = b'{"status":"ok","service":"alex-repo-simulator-mcp"}'
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
            ],
        })
        await send({"type": "http.response.body", "body": body})
        return
    await _mcp_app(scope, receive, send)


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        stateless_http=True,
        json_response=True,
    )
