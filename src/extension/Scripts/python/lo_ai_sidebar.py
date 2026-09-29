# -*- coding: utf-8 -*-
"""Sidebar integration components for the LibreOffice AI Assistant.

Registered as UNO components (manifest: uno-component;type=Python):

- org.sphaera.lo.ai.uifactory  : com.sun.star.ui.XUIElementFactory.
      Creates the panel content for ImplementationURL "loai.panel".
      Registered for the URL prefix "loai" via theUIElementFactoryManager
      (see StartupJob below and lo_ai_sidebar.register_factory()).
- org.sphaera.lo.ai.startupjob : com.sun.star.task.XJob. Run from the
      onFirstVisibleTask event (Jobs.xcu); registers the factory prefix.

The panel content is a compact chat view (lo_ai.ui.embed.EmbeddedPanel)
hosted in the sidebar-provided parent window.
"""

import os
import sys

import unohelper

import uno

from com.sun.star.awt import XWindow  # noqa: F401 (typing reference)
from com.sun.star.task import XJob
from com.sun.star.ui import XUIElement
from com.sun.star.ui import XUIElementFactory
from com.sun.star.lang import XServiceInfo

try:
    base = os.path.dirname(os.path.abspath(__file__))
except NameError:
    base = ""
_pp = os.path.join(base, "pythonpath")
if os.path.isdir(_pp) and _pp not in sys.path:
    sys.path.insert(0, _pp)

FACTORY_PREFIX = "loai"
FACTORY_SERVICE = "org.sphaera.lo.ai.uifactory"
JOB_SERVICE = "org.sphaera.lo.ai.startupjob"
PANEL_URL = "loai.panel"


def _ctx_from_args(args):
    for p in args:
        pass
    return None


def register_factory(ctx):
    """Register 'loai' URL type -> our factory service (all idempotent)."""
    ok = False
    try:
        smgr = ctx.getServiceManager()
        mgr = ctx.getValueByName(
            "/singletons/com.sun.star.ui.theUIElementFactoryManager")
        if mgr is None:
            mgr = smgr.createInstance("com.sun.star.ui.theUIElementFactoryManager")
        for a_type, a_name in (("loai", ""), ("loai", "panel")):
            try:
                # XUIElementFactoryRegistration.registerFactory(type, name, module, impl)
                mgr.registerFactory(a_type, a_name, "",
                                    "org.sphaera.lo.ai.uifactory")
                ok = True
            except Exception:
                pass  # ElementExistException: already registered
    except Exception as exc:
        try:
            from lo_ai.uno_env import default_config_dir
            directory = default_config_dir()
            os.makedirs(directory, exist_ok=True)
            with open(os.path.join(directory, "error.log"), "a",
                      encoding="utf-8") as fh:
                fh.write("---- sidebar register_factory: %r\n" % (exc,))
        except Exception:
            pass
    return ok


class _SidebarUIElement(unohelper.Base, XUIElement, XServiceInfo):
    def __init__(self, ctx, url, args, window, panel):
        self._ctx = ctx
        self._url = url
        self._args = args
        self._window = window
        self._panel = panel
        self._frame = None
        for prop in args:
            try:
                if prop.Name == "Frame":
                    self._frame = prop.Value
            except Exception:
                pass

    # XUIElement
    def getFrame(self):
        return self._frame

    def getResourceURL(self):
        return self._url

    def getObject(self):
        return self._window

    # XServiceInfo
    def getImplementationName(self):
        return "org.sphaera.lo.ai.uielement.impl"

    def supportsService(self, name):
        return False

    def getSupportedServiceNames(self):
        return ()


class _UIFactory(unohelper.Base, XUIElementFactory, XServiceInfo):
    def __init__(self, ctx):
        self._ctx = ctx

    def createUIElement(self, url, args):
        parent = None
        frame = None
        for prop in args:
            try:
                if prop.Name == "ParentWindow":
                    parent = prop.Value
                elif prop.Name == "Frame":
                    frame = prop.Value
            except Exception:
                pass
        if parent is None:
            return None
        try:
            from lo_ai.uno_env import resolve_config_dir
            from lo_ai.config import Config
            from lo_ai.i18n import set_lang
            from lo_ai.ui.embed import EmbeddedPanel
            smgr = self._ctx.getServiceManager()
            cfg = Config(resolve_config_dir(self._ctx, smgr))
            try:
                set_lang(cfg.data.get("ui_lang", "auto"), self._ctx, smgr)
            except Exception:
                pass
            panel = EmbeddedPanel(self._ctx, smgr, cfg, parent)
            return _SidebarUIElement(self._ctx, url, args,
                                     panel.dialog.getWindow(), panel)
        except Exception as exc:
            try:
                from lo_ai.uno_env import default_config_dir
                directory = default_config_dir()
                os.makedirs(directory, exist_ok=True)
                with open(os.path.join(directory, "error.log"), "a",
                          encoding="utf-8") as fh:
                    import traceback
                    fh.write("---- sidebar createUIElement: %r\n%s\n"
                             % (exc, traceback.format_exc()))
            except Exception:
                pass
            return None

    # XServiceInfo
    def getImplementationName(self):
        return "org.sphaera.lo.ai.uifactory.impl"

    def supportsService(self, name):
        return name == FACTORY_SERVICE

    def getSupportedServiceNames(self):
        return (FACTORY_SERVICE,)


def _dump_sidebar_config(ctx):
    """Diagnostic: what does the MERGED config contain for the sidebar?"""
    import os
    try:
        smgr = ctx.getServiceManager()
        cp = smgr.createInstanceWithArgumentsAndContext(
            "com.sun.star.configuration.ConfigurationProvider", (), ctx)

        def read(path):
            try:
                node = cp.createInstanceWithArguments(
                    "com.sun.star.configuration.ConfigurationAccess",
                    (_mkprop("nodepath", path),))
                return list(node.getElementNames())
            except Exception as exc:
                return ["ERROR: %r" % (exc,)]

        def _mkprop(name, value):
            prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
            prop.Name = name
            prop.Value = value
            return prop

        decks = read("/org.openoffice.Office.UI.Sidebar/Content/DeckList")
        panels = read("/org.openoffice.Office.UI.Sidebar/Content/PanelList")
        line = "---- sidebar config: decks=%s panels=%s" % (decks, panels)
        try:
            smgr2 = ctx.getServiceManager()
        except Exception:
            pass
        from lo_ai.uno_env import default_config_dir
        directory = default_config_dir()
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, "error.log"), "a",
                  encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception as exc:
        try:
            from lo_ai.uno_env import default_config_dir
            directory = default_config_dir()
            os.makedirs(directory, exist_ok=True)
            with open(os.path.join(directory, "error.log"), "a",
                      encoding="utf-8") as fh:
                fh.write("---- sidebar dump failed: %r\n" % (exc,))
        except Exception:
            pass


class _StartupJob(unohelper.Base, XJob, XServiceInfo):
    def __init__(self, ctx):
        self._ctx = ctx

    def execute(self, args):
        ok = register_factory(self._ctx)
        _dump_sidebar_config(self._ctx)
        try:
            from lo_ai.uno_env import default_config_dir
            directory = default_config_dir()
            os.makedirs(directory, exist_ok=True)
            with open(os.path.join(directory, "error.log"), "a",
                      encoding="utf-8") as fh:
                fh.write("---- startup job ran, factory registered=%s\n" % ok)
        except Exception:
            pass
        import uno
        return uno.Any("string", "ok")

    # XServiceInfo
    def getImplementationName(self):
        return "org.sphaera.lo.ai.startupjob.impl"

    def supportsService(self, name):
        return name == JOB_SERVICE

    def getSupportedServiceNames(self):
        return (JOB_SERVICE,)


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    _UIFactory, "org.sphaera.lo.ai.uifactory.impl", (FACTORY_SERVICE,))
g_ImplementationHelper.addImplementation(
    _StartupJob, "org.sphaera.lo.ai.startupjob.impl", (JOB_SERVICE,))
