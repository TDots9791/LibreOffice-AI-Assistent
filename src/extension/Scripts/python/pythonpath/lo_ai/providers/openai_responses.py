"""OpenAI Responses API adapter — required for Codex models.

Codex models (gpt-5-codex, codex-mini-latest, gpt-5.1-codex*) are served
through /v1/responses, not /chat/completions.
"""

from .. import http_client
from .base import Provider, ProviderError, wrap_errors


def to_input(messages):
    """Map chat messages to Responses-API input items."""
    items = []
    for msg in messages:
        role = msg.get("role")
        if role == "system":
            continue  # goes into `instructions`
        text = msg.get("content", "")
        content_type = "output_text" if role == "assistant" else "input_text"
        items.append({
            "role": role,
            "content": [{"type": content_type, "text": text}],
        })
    return items


class OpenAIResponsesProvider(Provider):
    api_style = "responses"

    def _url(self):
        if not self.base_url:
            raise ProviderError("Base URL is not configured.")
        return self.base_url + "/responses"

    def build_payload(self, messages, stream):
        system_lines = [m.get("content", "") for m in messages
                        if m.get("role") == "system"]
        payload = {
            "model": self.model,
            "input": to_input(messages),
            "stream": bool(stream),
        }
        instructions = "\n\n".join(s for s in system_lines if s)
        if instructions:
            payload["instructions"] = instructions
        if self.max_tokens:
            payload["max_output_tokens"] = self.max_tokens
        return payload  # temperature intentionally omitted: reasoning models reject it

    def complete(self, messages):
        payload = self.build_payload(messages, stream=False)
        data = wrap_errors(lambda: http_client.post_json(
            self._url(), self.auth_headers(), payload,
            timeout=min(self.timeout, 120), cancel=None))
        if data.get("status") == "failed":
            err = data.get("error") or {}
            raise ProviderError(err.get("message") or "response failed")
        try:
            return "".join(item.get("text", "")
                           for item in data.get("output", [])
                           if item.get("type") == "message"
                           for part in item.get("content", [])
                           if part.get("type") == "output_text")
        except (AttributeError, TypeError):
            raise ProviderError("Unexpected answer format: %s" % str(data)[:200])

    def stream_chat(self, messages, on_delta, cancel=None):
        if not self.streaming:
            text = self.complete(messages)
            if text:
                on_delta(text)
            return text

        payload = self.build_payload(messages, stream=True)
        collected = []

        def handle(event_name, data_str):
            obj = http_client.sse_parse_json(data_str)
            if obj is None:
                return
            etype = obj.get("type") or event_name
            if etype == "response.output_text.delta":
                chunk = obj.get("delta") or ""
                if chunk:
                    collected.append(chunk)
                    on_delta(chunk)
            elif etype == "response.failed":
                err = obj.get("response", {}).get("error") or {}
                raise ProviderError(err.get("message") or "response failed")
            elif etype == "error":
                raise ProviderError(obj.get("message") or "provider error")

        wrap_errors(lambda: http_client.post_stream(
            self._url(), self.auth_headers(), payload, handle,
            timeout=self.timeout, cancel=cancel))
        return "".join(collected)
