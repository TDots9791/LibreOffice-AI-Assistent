"""Persistent configuration for the LibreOffice AI Assistant.

This module is deliberately UNO-free so it can be unit-tested outside
LibreOffice. The caller (the UI layer) decides *where* the config lives:
inside the LibreOffice user profile when UNO is available, otherwise a
platform-specific fallback directory.
"""

import json
import os

CONFIG_FILENAME = "config.json"

DEFAULT_SYSTEM_PROMPT = (
    "You are an AI assistant embedded in LibreOffice. You help the user write, "
    "edit, translate, summarise and analyse the content of the document they are "
    "working on (Writer, Calc, Impress, Draw). Be concise and practical. "
    "Plain text is preferred; simple Markdown is acceptable when it improves "
    "readability. Always answer in the language the user writes in."
)

_DEFAULTS = {
    "ui_lang": "auto",
    "active_provider": "zai-coding",
    "include_context": True,
    "context_chars": 6000,
    "history_messages": 8,
    "providers": {},
}

_PROVIDER_DEFAULTS = {
    "base_url": "",
    "api_style": "openai",   # openai | anthropic | responses
    "model": "",
    "api_key": "",
    "temperature": 0.7,      # None means "do not send"
    "max_tokens": 0,         # 0 means "do not send"
    "timeout": 180,
    "system_prompt": "",     # empty -> DEFAULT_SYSTEM_PROMPT
    "streaming": True,
}


def default_config_dir():
    """Fallback location when no LibreOffice profile path is available."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, "lo-ai-assistant")
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "lo-ai-assistant")


class Config(object):
    def __init__(self, directory):
        self.directory = directory
        self.path = os.path.join(directory, CONFIG_FILENAME)
        self.data = json.loads(json.dumps(_DEFAULTS))  # deep copy
        self.load()

    # -- persistence -----------------------------------------------------
    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            if isinstance(stored, dict):
                self.data.update(stored)
                if not isinstance(self.data.get("providers"), dict):
                    self.data["providers"] = {}
        except (IOError, OSError, ValueError):
            pass  # missing or corrupt file -> defaults
        return self

    def save(self):
        try:
            os.makedirs(self.directory, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            try:
                os.chmod(self.path, 0o600)  # contains API keys
            except OSError:
                pass
        except (IOError, OSError) as exc:
            raise RuntimeError("Cannot save configuration: %s" % exc)
        return True

    # -- accessors --------------------------------------------------------
    @property
    def active_provider(self):
        return self.data.get("active_provider") or "zai-coding"

    @active_provider.setter
    def active_provider(self, pid):
        self.data["active_provider"] = pid

    def provider_settings(self, pid=None):
        pid = pid or self.active_provider
        stored = dict(_PROVIDER_DEFAULTS)
        stored.update(self.data["providers"].get(pid) or {})
        return stored

    def set_provider_settings(self, pid, settings):
        merged = dict(_PROVIDER_DEFAULTS)
        merged.update(self.data["providers"].get(pid) or {})
        for key in _PROVIDER_DEFAULTS:
            if key in settings:
                merged[key] = settings[key]
        self.data["providers"][pid] = merged
        return merged

    # -- convenience -------------------------------------------------------
    @staticmethod
    def coerce_int(value, default=0):
        try:
            n = int(str(value).strip())
            return n if n > 0 else default
        except (ValueError, TypeError, AttributeError):
            return default

    @staticmethod
    def coerce_float(value, default=None):
        s = str(value).strip() if value is not None else ""
        if not s:
            return default
        try:
            return float(s.replace(",", "."))
        except ValueError:
            return default

    @staticmethod
    def coerce_float_none(value):
        """Blank/invalid -> None (signals 'do not send the field')."""
        return Config.coerce_float(value, None)
