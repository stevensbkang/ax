#!/usr/bin/env python3
"""Model gateway for the AX demo.

Tasks send {system, prompt, maxTokens} to POST /v1/complete and get {text}.
Only the gateway holds the provider key, read from its Kubernetes Secret, so
nothing inside a sandbox can read or leak it. Usage is logged per task.
"""

import json
import os
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PROVIDER = os.environ["MODEL_PROVIDER"]  # anthropic or openai (any OpenAI-compatible API)
MODEL = os.environ["MODEL_NAME"]
API_KEY = os.environ["MODEL_API_KEY"]
DEFAULT_BASE_URLS = {
    "anthropic": "https://api.anthropic.com/v1",
    "openai": "https://api.openai.com/v1",
}
BASE_URL = os.environ.get("MODEL_BASE_URL") or DEFAULT_BASE_URLS[PROVIDER]
ANTHROPIC_VERSION = "2023-06-01"
PORT = 8080
TIMEOUT_SECONDS = 300


def post(url, headers, body):
    request = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.load(response)


def complete_anthropic(system, prompt, max_tokens):
    reply = post(
        f"{BASE_URL}/messages",
        {"x-api-key": API_KEY, "anthropic-version": ANTHROPIC_VERSION},
        {
            "model": MODEL,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
    )
    text = "".join(block.get("text", "") for block in reply["content"])
    return text, reply.get("usage", {})


def complete_openai(system, prompt, max_tokens):
    reply = post(
        f"{BASE_URL}/chat/completions",
        {"Authorization": f"Bearer {API_KEY}"},
        {
            "model": MODEL,
            "max_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        },
    )
    return reply["choices"][0]["message"]["content"], reply.get("usage", {})


COMPLETERS = {"anthropic": complete_anthropic, "openai": complete_openai}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            self.reply(200, {"status": "ok", "provider": PROVIDER, "model": MODEL})
        else:
            self.reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/v1/complete":
            self.reply(404, {"error": "not found"})
            return

        task = self.headers.get("X-AX-Task", "unknown")
        try:
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            text, usage = COMPLETERS[PROVIDER](
                request.get("system", ""), request["prompt"], int(request.get("maxTokens", 4000))
            )
        except Exception as err:  # the task sees why its call failed, never the key
            self.log_message("task=%s error=%s", task, err)
            self.reply(502, {"error": str(err)})
            return

        self.log_message("task=%s model=%s usage=%s", task, MODEL, json.dumps(usage))
        self.reply(200, {"text": text, "usage": usage})

    def reply(self, status, body):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()
