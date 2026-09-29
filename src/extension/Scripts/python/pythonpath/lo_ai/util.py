"""Small helpers shared across the extension (UNO-free)."""


def truncate(text, limit, marker="\n…[truncated]"):
    """Trim text to roughly `limit` characters, keeping whole lines when possible."""
    if not isinstance(text, str):
        text = str(text)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    nl = cut.rfind("\n")
    if nl > limit // 2:
        cut = cut[:nl]
    return cut + marker


def escape_for_prompt(text):
    """Light fencing so pasted document text is less likely to be read as instructions."""
    return text


def human_error(exc):
    """Best-effort single-line message from an arbitrary exception."""
    try:
        msg = str(exc)
    except Exception:
        msg = repr(exc)
    msg = " ".join(msg.split())
    return msg or exc.__class__.__name__
