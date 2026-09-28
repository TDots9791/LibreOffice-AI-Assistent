# -*- coding: utf-8 -*-
"""Scripting-framework entry points for the LibreOffice AI Assistant.

Referenced from Addons.xcu as:
  vnd.sun.star.script:ai_assistant_entry.py$<function>?language=Python&location=user:uno_packages/sphaera-lo-ai-assistant.oxt
"""

import os
import sys


def _bootstrap():
    try:
        base = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base = ""
    pp = os.path.join(base, "pythonpath")
    if os.path.isdir(pp) and pp not in sys.path:
        sys.path.insert(0, pp)


def _script_ctx():
    return XSCRIPTCONTEXT  # provided by the LibreOffice Scripting Framework


def _component_context():
    return _script_ctx().getComponentContext()


def _smgr():
    return _component_context().getServiceManager()


def get_config():
    _bootstrap()
    from lo_ai.config import Config
    from lo_ai.uno_env import resolve_config_dir
    return Config(resolve_config_dir(_component_context(), _smgr()))


def _error_box(exc):
    """Best-effort error dialog; falls back to stderr."""
    try:
        desktop = _smgr().createInstance("com.sun.star.frame.Desktop")
        model = desktop.getCurrentComponent()
        window = model.getCurrentController().getFrame().getContainerWindow()
        toolkit = _smgr().createInstance("com.sun.star.awt.Toolkit")
        box = toolkit.createMessageBox(window, "errorbox", 0,
                                       "AI Assistant", "%s" % exc)
        box.execute()
    except Exception:
        import traceback
        traceback.print_exc()


def open_panel(*args):
    """Show the assistant panel (Tools menu / toolbar)."""
    try:
        from lo_ai.ui.panel import show_panel
        show_panel(_component_context(), _smgr(), get_config())
    except Exception as exc:  # noqa: BLE001 - must not die silently in a menu
        _error_box(exc)


def open_settings(*args):
    """Show the provider settings dialog (Tools menu)."""
    try:
        from lo_ai.ui.settings_dialog import open_settings_for
        open_settings_for(_component_context(), _smgr(), get_config(), None)
    except Exception as exc:
        _error_box(exc)


def smoke_test(*args):
    """Headless self-check: package layout, imports and config writability.

    Returns a report string; usable from CLI:
      soffice vnd.sun.star.script:...$smoke_test?...
    """
    _bootstrap()
    report = []
    try:
        import lo_ai.version as v
        report.append("version=%s" % v.VERSION)
        cfg = get_config()
        cfg.save()
        marker = os.path.join(cfg.directory, "smoke-ok.txt")
        with open(marker, "w", encoding="utf-8") as fh:
            fh.write("smoke ok %s\n" % v.VERSION)
        report.append("config=%s" % cfg.path)

        from lo_ai import assistant as _assistant
        msgs = _assistant.build_messages("sys", [], "hello")
        assert msgs[0]["role"] == "system" and msgs[-1]["content"] == "hello"
        report.append("assistant=ok")

        from lo_ai.providers import create_provider
        p = create_provider({"api_style": "openai", "base_url": "http://invalid.invalid",
                             "model": "m"})
        report.append("provider=%s" % p.api_style)
        return "SMOKE OK: " + "; ".join(report)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return "SMOKE FAIL: %s | %s" % (exc, "; ".join(report))


def integration_test(*args):
    """In-process integration check (run via Basic/CLI, headless-safe).

    Verifies config writability, the document bridge on a hidden Writer
    document and the AsyncCallback pump service. Writes a report next to
    the config file and returns it.
    """
    _bootstrap()
    lines = []
    cfg_path = ""
    try:
        ctx = _component_context()
        smgr = _smgr()

        from lo_ai.config import Config
        from lo_ai.uno_env import resolve_config_dir
        cfg = Config(resolve_config_dir(ctx, smgr))
        cfg.save()
        cfg_path = cfg.path
        lines.append("config=writable")

        try:
            smgr.createInstance("com.sun.star.awt.AsyncCallback")
            lines.append("async_callback=present")
        except Exception as exc:
            lines.append("async_callback=missing(%s)" % exc)

        from lo_ai import document_bridge as db
        desktop = smgr.createInstance("com.sun.star.frame.Desktop")
        hidden = _smgr_prop("Hidden", True)
        doc = desktop.loadComponentFromURL(
            "private:factory/swriter", "_blank", 0, (hidden,))
        try:
            text = doc.getText()
            text.setString("First line.\nSecond line about AI.")
            cursor = text.createTextCursor()
            cursor.gotoStart(False)
            cursor.goRight(6, True)

            doc_ctx = db.collect_context(doc)
            lines.append("app_ok=%s" % (doc_ctx.app == "writer"))
            lines.append("selection_ok=%s" % (doc_ctx.selection_text == "First"))

            db.apply_text(doc, "REPLACED", "replace")
            lines.append("replace_ok=%s" %
                         doc.getText().getString().startswith("REPLACED line."))

            db.apply_text(doc, " APPENDED", "insert")
            lines.append("insert_ok=%s" %
                         doc.getText().getString().startswith("REPLACED APPENDED"))

            block = db.context_prompt_block(db.collect_context(doc))
            lines.append("context_ok=%s" % ("Writer" in block))
        finally:
            doc.close(False)

        ok = all(ln.split("=", 1)[1] not in ("False", "") for ln in lines
                 if "=" in ln and not ln.startswith("async_callback"))
        report = ("INTEGRATION OK: " if ok else "INTEGRATION FAIL: ") + "; ".join(lines)
    except Exception as exc:
        import traceback
        traceback.print_exc()
        report = "INTEGRATION FAIL: %r | %s" % (exc, "; ".join(lines))

    try:
        if cfg_path:
            with open(os.path.join(os.path.dirname(cfg_path),
                                   "integration-report.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write(report + "\n")
    except Exception:
        pass
    if "FAIL" in report:
        print(report)
    return report


def _smgr_prop(name, value):
    import uno
    prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    prop.Name = name
    prop.Value = value
    return prop


g_exportedScripts = (open_panel, open_settings, smoke_test, integration_test)
