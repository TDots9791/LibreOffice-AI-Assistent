#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local mock of the three chat APIs (SSE + JSON) for provider tests."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def _sse(event, data):
    if event:
        return "event: %s\ndata: %s\n\n" % (event, json.dumps(data))
    return "data: %s\n\n" % json.dumps(data)


class MockHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence test output
        pass

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except ValueError:
            return {}

    def _reply(self, status, payload, content_type="application/json"):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = self._read_body()
        auth = self.headers.get("Authorization", "") + self.headers.get("x-api-key", "")
        path = self.path

        if "badkey" in auth:
            self._reply(401, {"error": {"message": "invalid api key"}})
            return

        if path.endswith("/chat/completions"):
            if body.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for word in ("Hello", " ", "from", " chat"):
                    chunk = {"choices": [{"delta": {"content": word}}]}
                    self.wfile.write(("data: %s\n\n" % json.dumps(chunk)).encode())
                if body.get("messages") and "cancel" in json.dumps(body["messages"]):
                    self.wfile.write(("data: %s\n\n" % json.dumps(
                        {"choices": [{"delta": {"content": " MORE"}}]})).encode())
                self.wfile.write(b"data: [DONE]\n\n")
            else:
                self._reply(200, {"choices": [{"message": {
                    "role": "assistant",
                    "content": "Hello from chat"}}]})
            return

        if path.endswith("/messages"):  # Anthropic
            if body.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(_sse("message_start", {
                    "type": "message_start", "message": {}}).encode())
                self.wfile.write(_sse("content_block_delta", {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "Hi "}}).encode())
                self.wfile.write(_sse("content_block_delta", {
                    "type": "content_block_delta",
                    "delta": {"type": "text_delta", "text": "from claude"}}).encode())
                self.wfile.write(_sse("message_stop", {"type": "message_stop"}).encode())
            else:
                self._reply(200, {"content": [{"type": "text",
                                               "text": "Hi from claude"}]})
            return

        if path.endswith("/responses"):  # OpenAI Responses API (Codex)
            if body.get("stream"):
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                self.wfile.write(_sse("response.output_text.delta", {
                    "type": "response.output_text.delta", "delta": "Cod"}).encode())
                self.wfile.write(_sse("response.output_text.delta", {
                    "type": "response.output_text.delta", "delta": "ex!"}).encode())
                self.wfile.write(_sse("response.completed", {
                    "type": "response.completed",
                    "response": {"status": "completed"}}).encode())
            else:
                self._reply(200, {"status": "completed", "output": [
                    {"type": "message", "content": [
                        {"type": "output_text", "text": "Codex!"}]}]})
            return

        if path.endswith("/error"):
            self._reply(500, {"error": {"message": "boom"}})
            return

        self._reply(404, {"error": {"message": "unknown path %s" % path}})


def start_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, "http://127.0.0.1:%d" % server.server_address[1]
