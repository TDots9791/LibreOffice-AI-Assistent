"""OpenAI Chat Completions adapter.

Covers OpenAI itself plus every OpenAI-compatible service: Z.ai (GLM),
Gemini compatibility layer, OpenRouter, DeepSeek, Mistral, Groq, xAI,
Together, Fireworks, Perplexity, Ollama, LM Studio, vLLM, gateways.
"""

from .. import http_client
from . import base as _base
from .base import Provider, ProviderError, wrap_errors

# Models that only accept max_completion_tokens and reject sampling knobs.
_REASONING_PREFIXES = ("o1", "o3", "o4", "gpt-5", "codex")


def _is_reasoning_family(model):
    m = (model or "").lower()
    return m.startswith(_REASONING_PREFIXES)


def build_payload(provider, messages, stream, tools=None):
    payload = {
        "model": provider.model,
        "messages": messages,
        "stream": bool(stream),
    }
    if tools:
        payload["tools"] = [{"type": "function", "function": t}
                            for t in tools]
        payload["tool_choice"] = "auto"
    if provider.max_tokens:
        if _is_reasoning_family(provider.model):
            payload["max_completion_tokens"] = provider.max_tokens
        else:
            payload["max_tokens"] = provider.max_tokens
    if provider.temperature is not None and not _is_reasoning_family(provider.model):
        payload["temperature"] = provider.temperature
    return payload


def parse_turn(data):
    """AssistantTurn from a chat.completion (text and/or tool_calls)."""
    from .base import AssistantTurn
    try:
        message = data["choices"][0]["message"] or {}
    except (KeyError, IndexError, TypeError):
        raise ProviderError("Unexpected answer format: %s" % str(data)[:200])
    if isinstance(message.get("error"), dict):
        raise ProviderError(message["error"].get("message") or "provider error")
    calls = []
    for tc in message.get("tool_calls") or []:
        fn = tc.get("function") or {}
        calls.append({"id": tc.get("id") or fn.get("name") or "call",
                      "name": fn.get("name") or "",
                      "args": fn.get("arguments") or "{}"})
    return AssistantTurn(content=message.get("content"), tool_calls=calls)


def extract_delta(obj):
    """Content chunk from one chat.completion.chunk, or None."""
    if not isinstance(obj, dict):
        return None
    if obj.get("error"):
        err = obj["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        raise ProviderError(msg or "provider error")
    choices = obj.get("choices") or []
    if not choices:
        return None
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if content:
        return content
    # Some gateways stream the whole message instead of deltas.
    message = choices[0].get("message") or {}
    return message.get("content") or None


class OpenAICompatProvider(Provider):
    api_style = "openai"
    supports_tools = True

    def _url(self):
        if not self.base_url:
            raise ProviderError("Base URL is not configured.")
        return self.base_url + "/chat/completions"

    def _auth(self):
        headers = dict(self.extra_headers)
        if self.api_key:
            headers["Authorization"] = "Bearer %s" % self.api_key
        return headers

    def complete(self, messages):
        """Non-streaming helper (used by the connection test)."""
        payload = build_payload(self, messages, stream=False)
        data = wrap_errors(lambda: http_client.post_json(
            self._url(), self._auth(), payload,
            timeout=min(self.timeout, 120), cancel=None))
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise ProviderError("Unexpected answer format: %s" % str(data)[:200])

    def chat_with_tools(self, messages, tools, cancel=None):
        """One non-streaming turn with function calling (OpenAI shape)."""
        payload = build_payload(self, messages, stream=False, tools=tools)
        data = wrap_errors(lambda: http_client.post_json(
            self._url(), self._auth(), payload,
            timeout=self.timeout, cancel=cancel))
        return parse_turn(data)

    def stream_chat(self, messages, on_delta, cancel=None):
        if not self.streaming:
            text = self.complete(messages)
            if text:
                on_delta(text)
            return text

        payload = build_payload(self, messages, stream=True)
        collected = []

        def handle(event_name, data_str):
            obj = http_client.sse_parse_json(data_str)
            if obj is None:
                return
            chunk = extract_delta(obj)
            if chunk:
                collected.append(chunk)
                on_delta(chunk)

        wrap_errors(lambda: http_client.post_stream(
            self._url(), self._auth(), payload, handle,
            timeout=self.timeout, cancel=cancel))
        return "".join(collected)
