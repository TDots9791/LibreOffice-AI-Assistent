# -*- coding: utf-8 -*-
"""Entry points for the LibreOffice AI Assistant.

Two registration routes are provided:

1. Python UNO components (manifest: uno-component;type=Python) dispatched
   from menus via `service:` URLs — the APSO-proven route:
     service:org.sphaera.lo.ai.panel.impl    -> opens the assistant panel
     service:org.sphaera.lo.ai.settings.impl -> opens the settings dialog
   The loader passes the component context to __init__(ctx); there is NO
   XSCRIPTCONTEXT global on this route, so the context is stored globally
   here and reused by the plain functions.
2. Plain scripting-framework functions (g_exportedScripts) so the actions
   are also runnable from Tools > Macros (there XSCRIPTCONTEXT exists).
"""

import os
import sys
import traceback

VERSION_TEXT = "?"

_CTX = None  # component context, captured by the service components


def _set_version():
    global VERSION_TEXT
    try:
        from lo_ai.version import VERSION
        VERSION_TEXT = VERSION
    except Exception:
        pass


_set_version()


def _bootstrap():
    try:
        base = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base = ""
    pp = os.path.join(base, "pythonpath")
    if os.path.isdir(pp) and pp not in sys.path:
        sys.path.insert(0, pp)


def _component_context():
    if _CTX is not None:
        return _CTX
    return XSCRIPTCONTEXT.getComponentContext()  # scripting-framework route


def _smgr():
    return _component_context().getServiceManager()


def get_config():
    _bootstrap()
    from lo_ai.config import Config
    from lo_ai.uno_env import resolve_config_dir
    return Config(resolve_config_dir(_component_context(), _smgr()))


def _log_exception(context, exc):
    """Append failures to <config>/error.log — silent menus must not be mute."""
    try:
        _bootstrap()
        from lo_ai.uno_env import default_config_dir
        directory = default_config_dir()
        os.makedirs(directory, exist_ok=True)
        try:
            cfg_path = os.path.dirname(get_config().path)
            if os.path.isdir(cfg_path):
                directory = cfg_path
        except Exception:
            pass
        with open(os.path.join(directory, "error.log"), "a",
                  encoding="utf-8") as fh:
            fh.write("---- %s (%s)\n%s\n" % (
                context, exc, traceback.format_exc()))
    except Exception:
        traceback.print_exc()


def _error_box(exc):
    """Show the FULL traceback (file:line) so failures are actionable."""
    _log_exception("menu action", exc)
    try:
        tb = traceback.format_exc()
        text = ("%s\n\n%s" % (exc, tb))[-1800:]
        desktop = _smgr().createInstance("com.sun.star.frame.Desktop")
        model = desktop.getCurrentComponent()
        window = model.getCurrentController().getFrame().getContainerWindow()
        toolkit = _smgr().createInstance("com.sun.star.awt.Toolkit")
        box = toolkit.createMessageBox(window, "errorbox", 0,
                                       "AI Assistant", text)
        box.execute()
    except Exception:
        pass  # logged already


def _init_lang():
    try:
        cfg = get_config()
        from lo_ai.i18n import set_lang
        set_lang(cfg.data.get("ui_lang", "auto"), _component_context(), _smgr())
    except Exception:
        from lo_ai.i18n import set_lang
        set_lang("auto")


def _register_sidebar_factory():
    try:
        ctx = _component_context()
        mgr = ctx.getValueByName(
            "/singletons/com.sun.star.ui.theUIElementFactoryManager")
        if mgr is None:
            mgr = _smgr().createInstance("com.sun.star.ui.theUIElementFactoryManager")
        for a_type, a_name in (("loai", ""), ("loai", "panel")):
            try:
                mgr.registerFactory(a_type, a_name, "",
                                    "org.sphaera.lo.ai.uifactory")
            except Exception:
                pass  # already registered
    except Exception as exc:
        _log_exception("sidebar factory registration", exc)


def open_panel(*args):
    """Show the assistant panel: sidebar deck first, floating window fallback."""
    try:
        _log_line("open_panel click, v=%s" % VERSION_TEXT)
        _init_lang()
        _register_sidebar_factory()
        try:
            desktop = _smgr().createInstance("com.sun.star.frame.Desktop")
            model = desktop.getCurrentComponent()
            controller = model.getCurrentController()
            sidebar = None
            try:
                sidebar = controller.getSidebar()
            except Exception as exc:
                _log_exception("controller.getSidebar", exc)
            if sidebar is None:
                # The sidebar object is created lazily; make sure it exists.
                try:
                    helper = _smgr().createInstance(
                        "com.sun.star.frame.DispatchHelper")
                    helper.executeDispatch(controller.getFrame(),
                                           ".uno:Sidebar", "", 0, ())
                except Exception as exc:
                    _log_exception("dispatch .uno:Sidebar", exc)
                try:
                    sidebar = controller.getSidebar()
                except Exception as exc:
                    _log_exception("controller.getSidebar (2nd)", exc)
            if sidebar is None:
                raise RuntimeError("sidebar provider unavailable")
            sidebar.showDeck("LoAIDeck")
            _log_line("showDeck OK — sidebar deck opened")
            return  # docked panel opened — document stays visible
        except Exception as exc:
            _log_line("sidebar deck route FAILED -> floating fallback")
            _log_exception("sidebar deck route", exc)
        from lo_ai.ui.panel import show_panel
        show_panel(_component_context(), _smgr(), get_config())
    except Exception as exc:  # must not die silently from a menu click
        _error_box(exc)


def open_settings(*args):
    """Show the provider settings dialog."""
    try:
        _init_lang()
        _register_sidebar_factory()
        from lo_ai.i18n import tr
        from lo_ai.ui.settings_dialog import open_settings_for
        saved = open_settings_for(_component_context(), _smgr(), get_config(), None)
        if saved:
            desktop = _smgr().createInstance("com.sun.star.frame.Desktop")
            model = desktop.getCurrentComponent()
            window = model.getCurrentController().getFrame().getContainerWindow()
            toolkit = _smgr().createInstance("com.sun.star.awt.Toolkit")
            box = toolkit.createMessageBox(window, "infobox", 0,
                                           tr("saved_title"), tr("saved"))
            box.execute()
    except Exception as exc:
        _error_box(exc)


def smoke_test(*args):
    """Headless self-check: package layout, imports and config writability."""
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
        _log_exception("smoke_test", exc)
        return "SMOKE FAIL: %s | %s" % (exc, "; ".join(report))


g_exportedScripts = (open_panel, open_settings, smoke_test)

# --- service: URL components (menus dispatch these; APSO-style) -------------

try:
    import unohelper
    from com.sun.star.task import XJobExecutor
    from com.sun.star.lang import XServiceInfo

    _UNO_AVAILABLE = True
except Exception:  # tooling outside LibreOffice
    _UNO_AVAILABLE = False

if _UNO_AVAILABLE:
    class _JobBase(unohelper.Base, XJobExecutor, XServiceInfo):
        _IMPLEMENTATION_NAME = ""
        _SERVICE_NAME = ""
        _ACTION = None

        def __init__(self, ctx):
            # pythonloader passes the component context here; XSCRIPTCONTEXT
            # does not exist on this route.
            global _CTX
            _CTX = ctx

        def execute(self, *args):
            try:
                self._ACTION()
            except Exception as exc:  # noqa: BLE001
                _error_box(exc)

        # XServiceInfo
        def getImplementationName(self):
            return self._IMPLEMENTATION_NAME

        def supportsService(self, name):
            return name == self._SERVICE_NAME

        def getSupportedServiceNames(self):
            return (self._SERVICE_NAME,)

    class PanelJob(_JobBase):
        _IMPLEMENTATION_NAME = "org.sphaera.lo.ai.panel.impl"
        _SERVICE_NAME = "org.sphaera.lo.ai.panel"
        _ACTION = staticmethod(open_panel)

    class SettingsJob(_JobBase):
        _IMPLEMENTATION_NAME = "org.sphaera.lo.ai.settings.impl"
        _SERVICE_NAME = "org.sphaera.lo.ai.settings"
        _ACTION = staticmethod(open_settings)

    g_ImplementationHelper = unohelper.ImplementationHelper()
    g_ImplementationHelper.addImplementation(PanelJob,
                                             "org.sphaera.lo.ai.panel.impl",
                                             ("org.sphaera.lo.ai.panel",))
    g_ImplementationHelper.addImplementation(SettingsJob,
                                             "org.sphaera.lo.ai.settings.impl",
                                             ("org.sphaera.lo.ai.settings",))
