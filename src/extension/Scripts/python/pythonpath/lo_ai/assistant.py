"""Prompt building and chat orchestration (UNO-free)."""

from .i18n import tr
from .providers import create_provider

# action key -> prompt template (None = plain chat); labels come from i18n
ACTIONS = {
    "chat": None,
    "improve": "Improve this text: fix grammar, clarity and style, keep the "
               "original meaning and language. Return only the improved text.\n\n{text}",
    "grammar": "Fix grammar and spelling in this text. Return only the corrected "
               "text without commentary.\n\n{text}",
    "summarize": "Summarize the following text. Keep the key points.\n\n{text}",
    "translate": "Translate this text into {target_lang}. Return only the "
                 "translation.\n\n{text}",
    "explain": "Explain the following in clear, simple terms:\n\n{text}",
    "continue": "Continue writing this text, matching its style and language. "
                "Return only the continuation.\n\n{text}",
    "shorten": "Make this text more concise while keeping the key information. "
               "Return only the shortened text.\n\n{text}",
    "expand": "Expand this text with useful details, keeping its style and "
              "language. Return only the expanded text.\n\n{text}",
    "formal": "Rewrite this text in a formal, professional tone, keeping the "
              "language. Return only the rewritten text.\n\n{text}",
    "bullets": "Convert this text into concise bullet points (use '- ').\n\n{text}",
}


def action_label(key):
    return tr("act_" + key)


def action_labels():
    return tuple(action_label(k) for k in ACTION_ORDER)


def action_key_by_label(label):
    for k in ACTION_ORDER:
        if action_label(k) == label:
            return k
    return "chat"

ACTION_ORDER = ["chat", "improve", "grammar", "summarize", "translate", "explain",
                "continue", "shorten", "expand", "formal", "bullets"]

DEFAULT_TARGET_LANG = "English"


def build_user_message(action_key, user_text, context_block, target_lang=None):
    """Turn the UI inputs into the final user message for the model."""
    template = ACTIONS.get(action_key, ACTIONS["chat"])
    text = (user_text or "").strip()

    if action_key == "chat":
        message = text or "(empty message)"
    elif template is not None:
        source = text
        if not source:
            source = "(see document context)"
        message = template.replace("{text}", source)
        if "{target_lang}" in message:
            message = message.replace("{target_lang}", target_lang or DEFAULT_TARGET_LANG)
    else:
        message = text

    if context_block:
        message = message + "\n" + context_block
    return message


def build_messages(system_prompt, history, user_message):
    """system + trimmed history + the new user message."""
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    for item in history:
        role = item.get("role")
        content = item.get("content")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})
    return messages


def run_turn(provider_settings, messages, on_delta, cancel=None):
    """One assistant turn. Returns the full answer text."""
    provider = create_provider(provider_settings)
    return provider.stream_chat(messages, on_delta, cancel=cancel)
