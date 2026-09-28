"""Minimal HTTP client for chat APIs, standard library only.

LibreOffice ships its own Python without pip, so everything here uses
urllib + json + threading. Supports streamed Server-Sent-Events (SSE)
responses and cooperative cancellation via threading.Event.
"""

import json
import ssl
import threading
import urllib.error
import urllib.request


class Cancelled(Exception):
    """Raised when the user pressed Stop."""


class HttpError(Exception):
    def __init__(self, message, status=None, body=None):
        super(HttpError, self).__init__(message)
        self.status = status
        self.body = body or ""


def _extract_error_message(body):
    """Pull a human-readable message out of typical error JSON envelopes."""
    try:
        data = json.loads(body)
    except (ValueError, TypeError):
        return None
    if isinstance(data, dict):
        err = data.get("error")
        if isinstance(err, dict) and err.get("message"):
            return str(err["message"])
        if isinstance(err, str) and err:
            return err
        for key in ("message", "detail", "msg"):
            if data.get(key):
                return str(data[key])
    return None


def _build_request(url, headers, payload):
    body = json.dumps(payload).encode("utf-8")
    all_headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "lo-ai-assistant/1.0",
    }
    all_headers.update(headers or {})
    return urllib.request.Request(url, data=body, headers=all_headers, method="POST")


def _open(request, timeout, cancel):
    if cancel is not None and cancel.is_set():
        raise Cancelled()
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            pass
        msg = _extract_error_message(body) or ("HTTP %s" % exc.code)
        raise HttpError(msg, status=exc.code, body=body)
    except urllib.error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise HttpError("Connection failed: %s" % reason)
    except ssl.SSLError as exc:
        raise HttpError("TLS error: %s" % exc)


def post_json(url, headers, payload, timeout=120, cancel=None):
    """POST JSON, return the parsed JSON answer (non-streaming)."""
    request = _build_request(url, headers, payload)
    resp = _open(request, timeout, cancel)
    try:
        raw = resp.read()
    finally:
        try:
            resp.close()
        except Exception:
            pass
    text = raw.decode("utf-8", "replace")
    try:
        return json.loads(text)
    except ValueError:
        raise HttpError("Server returned non-JSON answer: %s" % text[:200])


def post_stream(url, headers, payload, on_event, timeout=180, cancel=None):
    """POST JSON and stream an SSE answer.

    `on_event(event_name, data_str)` is called for every SSE data block.
    Returns once the stream ends or `cancel` becomes set.
    """
    request = _build_request(url, headers, payload)
    resp = _open(request, timeout, cancel)
    event_name = ""
    data_lines = []
    try:
        for raw_line in resp:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            line = raw_line.decode("utf-8", "replace").rstrip("\r\n")
            if line == "":
                if data_lines:
                    on_event(event_name, "\n".join(data_lines))
                event_name = ""
                data_lines = []
                continue
            if line.startswith("event:"):
                event_name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:"):].strip())
            # comments (": keep-alive") and unknown fields are ignored
    finally:
        try:
            resp.close()
        except Exception:
            pass


def sse_parse_json(data_str):
    """Parse one SSE data block; '[DONE]' sentinels return None."""
    if not data_str or data_str == "[DONE]":
        return None
    try:
        return json.loads(data_str)
    except ValueError:
        return None
