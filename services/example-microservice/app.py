"""A tiny real microservice — the codebase-lane target for the `software-arch` demo.

Deliberately minimal and dependency-free (stdlib only) so CLI-Anything has a real,
self-contained codebase to make agent-native. Two endpoints over an in-memory store.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer

_ITEMS: dict[int, dict] = {}
_NEXT_ID = [1]


def create_item(name: str, qty: int = 1) -> dict:
    item = {"id": _NEXT_ID[0], "name": name, "qty": qty}
    _ITEMS[item["id"]] = item
    _NEXT_ID[0] += 1
    return item


def list_items() -> list[dict]:
    return list(_ITEMS.values())


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, payload) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path == "/items":
            self._send(200, list_items())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        if self.path == "/items":
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
            self._send(201, create_item(data.get("name", "unnamed"), data.get("qty", 1)))
        else:
            self._send(404, {"error": "not found"})


def serve(port: int = 8080) -> None:  # pragma: no cover - entrypoint
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":  # pragma: no cover
    serve()
