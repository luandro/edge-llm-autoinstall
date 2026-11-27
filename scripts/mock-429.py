#!/usr/bin/env python3
"""Local mock OpenAI-compatible endpoint for 429 / Retry-After rehearsal.

Returns 429 with Retry-After for the first N requests, then 200. Logs every
request to a local JSONL file. Contacts no real provider and never sees a key.

Usage:
  python3 scripts/mock-429.py --port 8099 --fail-first 2 --retry-after 1 --log /tmp/mock429.jsonl

Point a Hermes custom provider at http://127.0.0.1:8099/v1 and run one bounded
turn. Verify capped Retry-After, checkpoint resume and that no side-effectful
command is repeated. No cloud quota is consumed.
"""
from __future__ import annotations

import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

STATE: dict = {"count": 0}


def make_handler(fail_first: int, retry_after: str, log_path: str):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            is_chat = self.path.rstrip("/").endswith("/chat/completions")
            with lock:
                # Only chat requests consume the 429 budget; capability probes (/api/show)
                # must not silently exhaust it before the real turn.
                n = 0
                if is_chat:
                    STATE["count"] += 1
                    n = STATE["count"]
                entry = {
                    "n": n, "path": self.path, "content_length": length,
                    "authorization_present": bool(self.headers.get("Authorization")),
                    "ts": time.time(),
                }
                if log_path:
                    with open(log_path, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(entry) + "\n")
            if n <= fail_first:
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.send_header("Retry-After", retry_after)
                self.send_header("X-Ratelimit-Remaining-Requests", "0")
                self.end_headers()
                self.wfile.write(json.dumps({"error": {
                    "message": "Mock rate limit", "type": "rate_limit_error",
                    "retry_after": int(float(retry_after))}}).encode())
                return
            result = {
                "id": "chatcmpl-mock", "object": "chat.completion", "created": int(time.time()),
                "model": "mock-model",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            }
            wants_stream = b'"stream":true' in body.replace(b" ", b"") or b'"stream": true' in body
            if wants_stream:
                # Minimal OpenAI-compatible SSE: one content chunk, a finish chunk, [DONE].
                chunk = {"id": "chatcmpl-mock", "object": "chat.completion.chunk",
                         "created": int(time.time()), "model": "mock-model",
                         "choices": [{"index": 0, "delta": {"content": "OK"}, "finish_reason": None}]}
                final = {**chunk, "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                         "usage": result["usage"]}
                data = ("data: " + json.dumps(chunk) + "\n\n"
                        + "data: " + json.dumps(final) + "\n\n"
                        + "data: [DONE]\n\n").encode()
                ctype = "text/event-stream"
            else:
                data = json.dumps(result).encode()
                ctype = "application/json"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Ratelimit-Limit-Requests", "1000")
            self.send_header("X-Ratelimit-Limit-Tokens", "8000")
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args) -> None:
            pass

    return Handler


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=8099)
    p.add_argument("--fail-first", type=int, default=2)
    p.add_argument("--retry-after", default="1")
    p.add_argument("--log", default="")
    a = p.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", a.port),
                                 make_handler(a.fail_first, a.retry_after, a.log))
    print(f"mock 429 on 127.0.0.1:{a.port}; first {a.fail_first} requests 429; "
          f"Retry-After={a.retry_after}s", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
