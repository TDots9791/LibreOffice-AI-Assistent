"""Provider registry: api_style -> adapter class."""

from .anthropic import AnthropicProvider
from .base import Provider, ProviderError  # noqa: F401 (re-exported)
from .openai_compat import OpenAICompatProvider
from .openai_responses import OpenAIResponsesProvider
from .presets import PRESETS, PRESET_ORDER, get_preset, preset_labels  # noqa: F401

_API_STYLES = {
    "openai": OpenAICompatProvider,
    "anthropic": AnthropicProvider,
    "responses": OpenAIResponsesProvider,
}


def create_provider(settings):
    """Instantiate the adapter matching settings["api_style"]."""
    style = (settings.get("api_style") or "openai").lower()
    cls = _API_STYLES.get(style)
    if cls is None:
        raise ProviderError("Unknown API style: %s" % style)
    return cls(settings)


def create_for_preset(pid, config):
    """Build a provider from the stored settings of preset `pid`."""
    return create_provider(config.provider_settings(pid))
