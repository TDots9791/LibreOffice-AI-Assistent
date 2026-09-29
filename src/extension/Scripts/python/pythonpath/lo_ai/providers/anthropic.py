"""Anthropic Messages API adapter (Claude)."""

from .. import http_client
from .base import Provider, ProviderError, wrap_errors

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(Provider):
    api_style = "anthropic"

    def _url(self):
        if not self.base_url:
            raise ProviderError("Base URL is not configured.")
        return self.base_url + "/messages"

    def _headers(self):
        headers = dict(self.extra_headers)
        headers["anthropic-version"] = ANTHROPIC_VERSION
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    @staticmethod
    def split_messages(messages):
        system_chunks = []
        chat = []
        for msg in messages:
            if msg.get("role") == "system":
                system_chunks.append(msg.get("content", ""))
            else:
                chat.append({"role": msg.get("role"), "content": msg.get("content", "")})
        return "\n\n".join(s for s in system_chunks if s), chat

    def build_payload(self, messages, stream):
        system, chat = self.split_messages(messages)
        payload = {
            "model": self.model,
            "messages": chat,
            "max_tokens": self.max_tokens or DEFAULT_MAX_TOKENS,
            "stream": bool(stream),
        }
        if system:
            payload["system"] = system
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        return payload

    def list_models(self):
        from .. import http_client
        data = wrap_errors(lambda: http_client.get_json(
            self.base_url + "/models", self._headers(),
            timeout=min(self.timeout, 30), cancel=None))
        items = data.get("data") if isinstance(data, dict) else None
        return sorted({str(i.get("id")) for i in (items or [])
                       if isinstance(i, dict) and i.get("id")})

    def complete(self, messages):
        payload = self.build_payload(messages, stream=False)
        data = wrap_errors(lambda: http_client.post_json(
            self._url(), self._headers(), payload,
            timeout=min(self.timeout, 120), cancel=None))
        try:
            parts = [blk.get("text", "") for blk in data.get("content", [])
                     if blk.get("type") == "text"]
            return "".join(parts)
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
            if etype == "error":
                err = obj.get("error") or {}
                raise ProviderError(err.get("message") or "provider error")
            if etype == "content_block_delta":
                delta = obj.get("delta") or {}
                if delta.get("type") in ("text_delta", "text"):
                    text = delta.get("text") or ""
                    if text:
                        collected.append(text)
                        on_delta(text)
            elif etype == "content_block":
                block = obj.get("content_block") or {}
                if block.get("type") == "text" and block.get("text"):
                    collected.append(block["text"])
                    on_delta(block["text"])

        wrap_errors(lambda: http_client.post_stream(
            self._url(), self._headers(), payload, handle,
            timeout=self.timeout, cancel=cancel))
        return "".join(collected)
