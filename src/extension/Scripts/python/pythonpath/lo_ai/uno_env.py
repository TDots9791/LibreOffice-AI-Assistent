"""Helpers for running inside LibreOffice: config path resolution, URL mapping."""

import os
from .config import default_config_dir

CONFIG_SUBDIR = "lo-ai-assistant"


def uno_url_to_path(url):
    """Best-effort file URL -> filesystem path (handles pathname protocol)."""
    if not url:
        return ""
    url = str(url).strip()
    if url.startswith("vnd.sun.star.pathname:"):
        return url[len("vnd.sun.star.pathname:"):]
    if url.startswith("file:"):
        try:
            from urllib.parse import unquote, urlparse
            path = unquote(urlparse(url).path)
            # Windows file:///C:/... -> C:/...
            if len(path) > 2 and path[0] == "/" and path[2] == ":":
                path = path[1:]
            return path
        except Exception:
            return ""
    return url if os.path.isabs(url) else ""


def resolve_config_dir(ctx, smgr):
    """Prefer the LibreOffice user profile (works in flatpak too)."""
    try:
        ps = smgr.createInstance("com.sun.star.util.PathSettings")
        path = uno_url_to_path(ps.getPropertyValue("UserConfig"))
        if path:
            return os.path.join(path, CONFIG_SUBDIR)
    except Exception:
        pass
    return default_config_dir()
