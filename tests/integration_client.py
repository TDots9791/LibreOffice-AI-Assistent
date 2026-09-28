#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Integration test, executed INSIDE the LibreOffice flatpak sandbox.

This LO 26.8 flatpak build kills remote URP bridges ~1-2 s after they are
established (an environment quirk unrelated to the extension; GUI usage is
in-process and unaffected). Therefore this client batches ALL remote calls
into one tight sequence immediately after connecting and prints the report
at the end.

Verified here:
  1. document_bridge on a real hidden Writer document (context, replace,
     insert, prompt block),
  2. the extension's script URL resolves through the ScriptProvider
     (proves unopkg registration + Addons.xcu URL scheme),
  3. the installed entry module runs smoke_test() (imports, config write),
  4. the AsyncCallback main-thread pump service is available.
"""

import glob
import os
import sys
import time

import uno
import unohelper  # noqa: F401

SCRIPT_URL = ("vnd.sun.star.script:ai_assistant_entry.py$smoke_test"
              "?language=Python&location=user:uno_packages/sphaera-lo-ai-assistant.oxt")

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((ok, name, detail))


class FakeScriptContext(object):
    def __init__(self, cc):
        self._cc = cc

    def getComponentContext(self):
        return self._cc


def installed_ext(profile):
    pats = [
        profile + "/user/uno_packages/cache/uno_packages/*/"
                  "sphaera-lo-ai-assistant.oxt",
        "/home/*/.config/libreoffice/4/user/uno_packages/cache/"
        "uno_packages/*/sphaera-lo-ai-assistant.oxt",
        "/home/*/.var/app/org.libreoffice.LibreOffice/config/libreoffice/"
        "4/user/uno_packages/cache/uno_packages/*/sphaera-lo-ai-assistant.oxt",
    ]
    found = []
    for pat in pats:
        found.extend(glob.glob(pat))
    return found[0] if found else None


def main():
    profile = os.environ.get("LOAI_PROFILE", "")
    port = os.environ.get("LOAI_PORT", "2004")

    local = uno.getComponentContext()
    resolver = local.ServiceManager.createInstanceWithContext(
        "com.sun.star.bridge.UnoUrlResolver", local)
    ctx = resolver.resolve(
        "uno:socket,host=127.0.0.1,port=%s;urp;StarOffice.ComponentContext" % port)
    smgr = ctx.ServiceManager
    desktop = smgr.createInstance("com.sun.star.frame.Desktop")

    ext_dir = installed_ext(profile)
    check("extension unpacked in profile", bool(ext_dir), ext_dir or "not found")

    # ---- 1. document bridge (batched first: the bridge dies young) ----
    try:
        sys.path.insert(0, os.path.join(ext_dir, "pythonpath"))
        from lo_ai import document_bridge as db

        hidden = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        hidden.Name = "Hidden"
        hidden.Value = True
        doc = desktop.loadComponentFromURL(
            "private:factory/swriter", "_blank", 0, (hidden,))
        text = doc.getText()
        text.setString("First line.\nSecond line about AI.")
        cursor = text.createTextCursor()
        cursor.gotoStart(False)
        cursor.goRight(6, True)  # select "First"

        doc_ctx = db.collect_context(doc)
        check("detect writer", doc_ctx.app == "writer", doc_ctx.app)
        check("selection text", doc_ctx.selection_text == "First",
              repr(doc_ctx.selection_text))

        db.apply_text(doc, "REPLACED", "replace")
        check("replace selection",
              doc.getText().getString().startswith("REPLACED line."),
              doc.getText().getString()[:40])

        db.apply_text(doc, " APPENDED", "insert")
        content = doc.getText().getString()
        check("insert at cursor", content.startswith("REPLACED APPENDED"), content[:40])

        block = db.context_prompt_block(db.collect_context(doc))
        check("context block", "Writer" in block, block[:50].replace("\n", " | "))
        doc.close(False)
    except Exception as exc:
        check("document bridge", False, repr(exc))

    # ---- 2. script URL resolution (ScriptProvider) ----
    try:
        factory = smgr.createInstance(
            "com.sun.star.script.provider.MasterScriptProviderFactory")
        provider = factory.createScriptProvider("")
        script = provider.getScript(SCRIPT_URL)
        check("script URL resolves", script is not None, "getScript OK")
    except Exception as exc:
        check("script URL resolves", False, repr(exc))

    # ---- 3. entry module smoke test (in-process, remote ctx) ----
    try:
        entry_path = os.path.join(ext_dir, "ai_assistant_entry.py")
        sys.path.insert(0, os.path.join(ext_dir, "pythonpath"))
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ai_assistant_entry_installed", entry_path)
        entry = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(entry)
        entry.XSCRIPTCONTEXT = FakeScriptContext(ctx)
        report = entry.smoke_test()
        check("smoke_test()", "SMOKE OK" in str(report), str(report))
    except Exception as exc:
        check("smoke_test()", False, repr(exc))

    # ---- 4. AsyncCallback (main-thread pump for streaming) ----
    try:
        svc = smgr.createInstance("com.sun.star.awt.AsyncCallback")
        check("AsyncCallback service",
              svc is not None and hasattr(svc, "addCallback"), "addCallback present")
    except Exception as exc:
        check("AsyncCallback service", False, repr(exc))

    time.sleep(0.2)  # let the last URP replies settle before printing
    print("=====")
    failed = [name for ok, name, _d in RESULTS if not ok]
    for ok, name, detail in RESULTS:
        print("%s %s%s" % ("PASS" if ok else "FAIL", name,
                           (" :: " + detail) if detail else ""))
    print("INTEGRATION %s" % ("FAILED: " + ", ".join(failed) if failed else "OK"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
