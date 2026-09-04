"""Loopback-only, read-only journal dashboard. Never imports broker or model clients."""

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "dashboard"


def journal_snapshot(path: Path = ROOT / ".local/onespread/journal.sqlite3") -> dict:
    events = []
    if path.exists():
        with sqlite3.connect(f"file:{quote(str(path))}?mode=ro", uri=True, timeout=2) as db:
            rows = db.execute("SELECT payload FROM events ORDER BY seq DESC LIMIT 100").fetchall()
        allowed = {
            "timestamp",
            "action",
            "reasons",
            "mode",
            "feed",
            "decision",
            "evidence",
            "refreshed_premium_usd",
            "indicative_exit_credit",
            "error_type",
        }
        events = [
            {k: v for k, v in json.loads(row[0]).items() if k in allowed} for row in reversed(rows)
        ]
    return {
        "source": "local_journal",
        "generated_at": datetime.now(UTC).isoformat(),
        "model_source": "GLM-5 when inference is reached",
        "events": events,
        "notice": "Read-only journal. Refreshing this view does not run the agent or place orders.",
    }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        # Refuse foreign Host headers and expose only a fixed file allowlist.
        host = self.headers.get("Host", "").split(":")[0]
        if host not in {"127.0.0.1", "localhost"}:
            self.send_error(403)
            return
        path = urlsplit(self.path).path
        if path == "/api/status":
            try:
                body, content_type = json.dumps(journal_snapshot()).encode(), "application/json"
            except (sqlite3.Error, ValueError):
                self.send_error(503, "Journal is temporarily unavailable")
                return
        else:
            files = {
                "/": ("index.html", "text/html"),
                "/app.js": ("app.js", "text/javascript"),
                "/style.css": ("style.css", "text/css"),
                "/demo.json": ("demo.json", "application/json"),
            }
            if path not in files:
                self.send_error(404)
                return
            name, content_type = files[path]
            body = (WEB / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'self'; base-uri 'none'",
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only OneSpread dashboard")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"OneSpread dashboard: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == "__main__":
    main()
