"""Provider base class shared by all API adapters."""

from .. import http_client
from ..util import human_error

try:
    import util as _util
except ImportError:
    from .. import util as _util


class ProviderError(Exception):
    """User-presentable provider failure."""

    def __init__(self, message, status=None):
        super(ProviderError, self).__init__(message)
        self.status = status


class AssistantTurn(object):
    """One model turn: text and/or requested tool calls.

    tool_calls items: {"id": str, "name": str, "args": str} — args is the
    raw JSON string as the model produced it (parsed by the caller).
    """

    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = list(tool_calls or [])

    @property
    def has_tool_calls(self):
        return bool(self.tool_calls)


def wrap_errors(fn):
    """Turn transport errors into ProviderError for the UI layer."""
    try:
        return fn()
    except http_client.Cancelled:
        raise
    except http_client.HttpError as exc:
        hint = ""
        if exc.status in (401, 403):
            hint = " Check the API key."
        elif exc.status == 429:
            hint = " Rate limit or quota exceeded."
        elif exc.status == 404:
            hint = " Check the base URL and model name."
        raise ProviderError(str(exc) + hint, status=exc.status)
    except Exception as exc:  # socket.timeout etc.
        raise ProviderError(human_error(exc))


class Provider(object):
    """Abstract chat provider. `stream_chat` must return the full answer."""

    api_style = "abstract"
    supports_tools = False

    def __init__(self, settings):
        self.base_url = (settings.get("base_url") or "").rstrip("/")
        self.model = settings.get("model") or ""
        self.api_key = settings.get("api_key") or ""
        self.temperature = settings.get("temperature")
        self.max_tokens = settings.get("max_tokens") or 0
        self.timeout = settings.get("timeout") or 180
        self.system_prompt = settings.get("system_prompt") or ""
        self.streaming = settings.get("streaming", True)
        self.extra_headers = settings.get("extra_headers") or {}

    @property
    def name(self):
        return "%s (%s)" % (self.api_style, self.model or "no model")

    def auth_headers(self):
        headers = dict(self.extra_headers)
        if self.api_key:
            headers["Authorization"] = "Bearer %s" % self.api_key
        return headers

    def stream_chat(self, messages, on_delta, cancel=None):
        raise NotImplementedError

    def chat_with_tools(self, messages, tools, cancel=None):
        """Non-streaming turn with function calling. `tools` is a list of
        {"name","description","parameters"} specs. Returns AssistantTurn;
        messages may contain assistant tool_calls and role="tool" results.
        Implemented only where the API style supports it."""
        raise NotImplementedError("tool calling not supported by %s"
                                  % self.api_style)

    def list_models(self):
        """Live model ids from GET {base_url}/models (OpenAI/Anthropic shape)."""
        from .. import http_client
        data = wrap_errors(lambda: http_client.get_json(
            self.base_url + "/models", self.auth_headers(),
            timeout=min(self.timeout, 30), cancel=None))
        items = data.get("data") if isinstance(data, dict) else None
        if items is None and isinstance(data, list):
            items = data
        ids = sorted({str(i.get("id")) for i in (items or [])
                      if isinstance(i, dict) and i.get("id")})
        return ids
