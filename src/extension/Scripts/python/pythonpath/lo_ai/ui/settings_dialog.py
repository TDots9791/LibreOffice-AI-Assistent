"""Settings dialog: provider preset, endpoint, model, key, generation knobs."""

import threading

from ..i18n import tr
from ..util import human_error, truncate
from .dialog_util import (XActionListener, XItemListener, add_control,
                          make_dialog, string_seq)

try:
    import unohelper
except Exception:
    class unohelper(object):
        class Base(object):
            pass


def _log_error(text):
    """Append to ~/.config/lo-ai-assistant/error.log (no UNO involved)."""
    try:
        import os
        from ..uno_env import default_config_dir
        directory = default_config_dir()
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, "error.log"), "a",
                  encoding="utf-8") as fh:
            fh.write("---- settings: %s\n" % text)
    except Exception:
        pass


def _message_box(smgr, window, kind, title, text):
    try:
        toolkit = smgr.createInstance("com.sun.star.awt.Toolkit")
        box = toolkit.createMessageBox(window, kind, 0, title, text)
        box.execute()
    except Exception:
        _log_error("message box failed: %s" % text)


def _doc_window(smgr):
    try:
        desktop = smgr.createInstance("com.sun.star.frame.Desktop")
        model = desktop.getCurrentComponent()
        return model.getCurrentController().getFrame().getContainerWindow()
    except Exception:
        return None


class _SaveHandler(unohelper.Base, XActionListener):
    def __init__(self, dlg):
        self.dlg = dlg

    def actionPerformed(self, *args):
        self.dlg.on_save()


class _CancelHandler(unohelper.Base, XActionListener):
    def __init__(self, dlg):
        self.dlg = dlg

    def actionPerformed(self, *args):
        self.dlg.on_cancel()


class _TestHandler(unohelper.Base, XActionListener):
    def __init__(self, dlg):
        self.dlg = dlg

    def actionPerformed(self, *args):
        self.dlg.on_test()


class _PresetHandler(unohelper.Base, XItemListener):
    def __init__(self, dlg):
        self.dlg = dlg

    def itemStateChanged(self, *args):
        self.dlg.on_preset_changed()

    def disposing(self, *args):
        pass


class _RefreshHandler(unohelper.Base, XActionListener):
    def __init__(self, dlg):
        self.dlg = dlg

    def actionPerformed(self, *args):
        self.dlg.on_refresh_models()


class SettingsDialog(object):
    WIDTH = 520
    HEIGHT = 476

    def __init__(self, ctx, smgr, config, pid):
        self.ctx = ctx
        self.smgr = smgr
        self.config = config
        self.pid = pid or config.active_provider
        self.saved = False
        self._models_busy = False
        self._build()

    def _build(self):
        from ..providers import preset_labels
        W = self.WIDTH

        self.dialog, m = make_dialog(self.smgr, tr("title_settings"), W, self.HEIGHT)

        add_control(m, "FixedText", "lblPreset", {"Label": tr("preset")}, 8, 9, 90, 12)
        labels = tuple(label for _p, label in preset_labels())
        add_control(m, "ComboBox", "cmbPreset",
                    {"Dropdown": True, "StringItemList": labels,
                     "Text": self._label_for_pid(self.pid)},
                    100, 6, W - 110, 12)

        self.lblNote = add_control(m, "FixedText", "lblNote",
                                   {"Label": "", "MultiLine": True},
                                   100, 20, W - 110, 22)

        add_control(m, "FixedText", "lblUrl", {"Label": "Base URL:"}, 8, 48, 90, 12)
        add_control(m, "Edit", "txtUrl", {"Text": ""}, 100, 45, W - 110, 12)

        add_control(m, "FixedText", "lblStyle", {"Label": tr("api_style")}, 8, 68, 90, 12)
        add_control(m, "ComboBox", "cmbStyle",
                    {"Dropdown": True,
                     "StringItemList": ("openai", "responses", "anthropic")},
                    100, 65, 120, 12)

        add_control(m, "FixedText", "lblModel", {"Label": tr("model")}, 8, 88, 90, 12)
        add_control(m, "ComboBox", "cmbModel", {"Dropdown": True},
                    100, 85, W - 186, 12)
        add_control(m, "Button", "btnModels", {"Label": tr("refresh")},
                    W - 82, 84, 74, 14)

        add_control(m, "FixedText", "lblKey", {"Label": tr("api_key")}, 8, 108, 90, 12)
        add_control(m, "Edit", "txtKey", {"EchoChar": 42}, 100, 105, W - 110, 12)
        add_control(m, "FixedText", "lblKeyHint",
                    {"Label": tr("key_hint"), "MultiLine": True},
                    100, 119, W - 110, 16)

        add_control(m, "FixedText", "lblTemp", {"Label": tr("temperature")}, 8, 142, 90, 12)
        add_control(m, "Edit", "txtTemp", {"Text": ""}, 100, 139, 60, 12)
        add_control(m, "FixedText", "lblTempHint", {"Label": tr("temp_hint")},
                    166, 142, W - 174, 12)

        add_control(m, "FixedText", "lblMax", {"Label": tr("max_tokens")}, 8, 162, 90, 12)
        add_control(m, "Edit", "txtMax", {"Text": ""}, 100, 159, 60, 12)
        add_control(m, "FixedText", "lblMaxHint", {"Label": tr("max_hint")},
                    166, 162, W - 174, 12)

        add_control(m, "FixedText", "lblTimeout", {"Label": tr("timeout")}, 8, 182, 90, 12)
        add_control(m, "Edit", "txtTimeout", {"Text": "180"}, 100, 179, 60, 12)

        add_control(m, "FixedText", "lblPanelSize",
                    {"Label": "Размер панели, px (ширина × высота):"},
                    8, 202, 220, 12)
        add_control(m, "Edit", "txtPanelW", {"Text": "380"}, 232, 200, 60, 12)
        add_control(m, "Edit", "txtPanelH", {"Text": "344"}, 300, 200, 60, 12)
        add_control(m, "FixedText", "lblPanelHint",
                    {"Label": "Прозрачность окна не поддерживается этой сборкой LibreOffice."},
                    8, 218, W - 16, 10)

        add_control(m, "CheckBox", "chkStream",
                    {"Label": tr("stream"), "State": 1},
                    8, 234, 300, 10)

        add_control(m, "FixedText", "lblSys", {"Label": tr("system_prompt")}, 8, 252, 200, 12)
        add_control(m, "Edit", "txtSys",
                    {"MultiLine": True, "VScroll": True},
                    8, 266, W - 16, 88)

        self.lblTest = add_control(m, "FixedText", "lblTest", {"Label": ""}, 8, 360, W - 16, 14)
        add_control(m, "Button", "btnTest", {"Label": tr("test_connection")}, 8, 378, 130, 16)

        add_control(m, "Button", "btnSave", {"Label": tr("save"), "Default": True},
                    W - 214, 378, 100, 16)
        add_control(m, "Button", "btnCancel", {"Label": tr("cancel")}, W - 108, 378, 100, 16)

        self.dialog.getControl("btnSave").addActionListener(_SaveHandler(self))
        self.dialog.getControl("btnCancel").addActionListener(_CancelHandler(self))
        self.dialog.getControl("btnTest").addActionListener(_TestHandler(self))
        self.dialog.getControl("btnModels").addActionListener(_RefreshHandler(self))
        self.dialog.getControl("cmbPreset").addItemListener(_PresetHandler(self))

        self._load_pid(self.pid)

    # --- helpers ---------------------------------------------------------------
    def _label_for_pid(self, pid):
        from ..providers import preset_labels, get_preset
        for p, label in preset_labels():
            if p == pid:
                return label
        return get_preset(self.pid)["label"]

    def _pid_for_label(self, label):
        from ..providers import preset_labels
        for p, lab in preset_labels():
            if lab == label:
                return p
        return None

    def _ctl_text(self, name):
        return self.dialog.getControl(name).getText()

    def _set_test_label(self, text):
        try:
            self.lblTest.setPropertyValue("Label", text)
        except Exception:
            _log_error("lblTest update failed: %s" % text)

    def _set_model_items(self, models):
        self.dialog.getControl("cmbModel").getModel().setPropertyValue(
            "StringItemList", string_seq(models))

    def _load_pid(self, pid):
        from ..providers import get_preset
        self.pid = pid
        preset = get_preset(pid)
        settings = self.config.provider_settings(pid)
        try:
            self.dialog.getControl("lblNote").getModel().setPropertyValue(
                "Label", preset.get("note") or "")
        except Exception:
            pass
        base = settings.get("base_url") or preset.get("base_url") or ""
        self.dialog.getControl("txtUrl").setText(base)
        self.dialog.getControl("cmbStyle").setText(
            settings.get("api_style") or preset["api_style"])
        models = list(preset.get("models", []))
        if settings.get("model") and settings["model"] not in models:
            models.insert(0, settings["model"])
        self._set_model_items(models)
        self.dialog.getControl("cmbModel").setText(settings.get("model", ""))
        self.dialog.getControl("txtKey").setText(settings.get("api_key") or "")
        temp = settings.get("temperature")
        self.dialog.getControl("txtTemp").setText("" if temp is None else str(temp))
        maxt = settings.get("max_tokens") or 0
        self.dialog.getControl("txtMax").setText(str(maxt) if maxt else "")
        self.dialog.getControl("txtTimeout").setText(str(settings.get("timeout") or 180))
        self.dialog.getControl("chkStream").setState(
            1 if settings.get("streaming", True) else 0)
        self.dialog.getControl("txtSys").setText(settings.get("system_prompt") or "")
        try:
            self.dialog.getControl("txtPanelW").setText(
                str(self.config.data.get("panel_width") or 380))
            self.dialog.getControl("txtPanelH").setText(
                str(self.config.data.get("panel_height") or 344))
        except Exception:
            pass

    # --- events -------------------------------------------------------------------
    def on_preset_changed(self):
        pid = self._pid_for_label(self._ctl_text("cmbPreset"))
        if pid:
            self._load_pid(pid)

    def _collect(self):
        from ..providers import get_preset
        pid = self._pid_for_label(self._ctl_text("cmbPreset")) or self.pid
        preset = get_preset(pid)
        timeout = self.config.coerce_int(self._ctl_text("txtTimeout"), 180)
        return pid, {
            "base_url": self._ctl_text("txtUrl").strip() or preset.get("base_url", ""),
            "api_style": self._ctl_text("cmbStyle").strip() or preset["api_style"],
            "model": self._ctl_text("cmbModel").strip(),
            "api_key": self._ctl_text("txtKey").strip(),
            "temperature": self.config.coerce_float_none(self._ctl_text("txtTemp")),
            "max_tokens": self.config.coerce_int(self._ctl_text("txtMax"), 0),
            "timeout": timeout if timeout > 0 else 180,
            "streaming": bool(self.dialog.getControl("chkStream").getState()),
            "system_prompt": self._ctl_text("txtSys"),
        }

    def on_save(self):
        try:
            pid, settings = self._collect()
            if not settings["base_url"]:
                _message_box(self.smgr, _doc_window(self.smgr), "warningbox",
                             tr("title_settings"), tr("base_url_required"))
                return
            self.config.set_provider_settings(pid, settings)
            self.config.active_provider = pid
            self.config.data["panel_width"] = self.config.coerce_int(
                self._ctl_text("txtPanelW"), 380)
            self.config.data["panel_height"] = self.config.coerce_int(
                self._ctl_text("txtPanelH"), 344)
            self.config.save()
            self.saved = True
            self.pid = pid
            self.dialog.endDialog(1)
        except Exception as exc:
            _log_error("on_save failed: %s\n%s" % (exc, human_error(exc)))
            _message_box(self.smgr, _doc_window(self.smgr), "errorbox",
                         tr("title_settings"),
                         "%s\n\n%s" % (tr("fail") + truncate(human_error(exc), 200),
                                       "see error.log"))

    def on_cancel(self):
        try:
            self.dialog.endDialog(0)
        except Exception:
            _log_error("on_cancel failed")

    def on_test(self):
        if getattr(self, "_test_busy", False):
            return
        self._test_busy = True
        pid, settings = self._collect()
        self._set_test_label(tr("testing"))
        worker = threading.Thread(target=self._test_worker, args=(settings,))
        worker.daemon = True
        worker.start()

    def _test_worker(self, settings):
        ok = False
        try:
            from ..providers import create_provider
            provider = create_provider(settings)
            messages = [{"role": "system", "content": "You are a connection test."},
                        {"role": "user", "content": "Reply with exactly: OK"}]
            settings = dict(settings)
            settings["streaming"] = False
            provider.streaming = False
            if hasattr(provider, "max_tokens"):
                provider.max_tokens = 8
            answer = provider.complete(messages) if hasattr(provider, "complete") \
                else provider.stream_chat(messages, lambda s: None)
            ok = (answer or "").strip() != ""
            msg = tr("connected") + truncate((answer or "").strip(), 60)
            if ok:
                try:
                    ids = create_provider(settings).list_models()
                    if ids:
                        self._set_model_items(ids)
                        msg += "  ·  %s %d" % (tr("models_loaded"), len(ids))
                except Exception:
                    pass
        except Exception as exc:
            msg = tr("fail") + truncate(human_error(exc), 160)
        self._test_busy = False
        self._set_test_label(msg)

    def on_refresh_models(self):
        if self._models_busy:
            return
        self._models_busy = True
        pid, settings = self._collect()
        self._set_test_label(tr("loading_models"))
        worker = threading.Thread(target=self._models_worker, args=(settings,))
        worker.daemon = True
        worker.start()

    def _models_worker(self, settings):
        try:
            from ..providers import create_provider
            provider = create_provider(settings)
            ids = provider.list_models()
            saved = settings.get("model", "")
            if saved and saved not in ids:
                ids.insert(0, saved)
            self._set_model_items(ids)
            if ids:
                self._set_test_label("%s %d" % (tr("models_loaded"), len(ids)))
            else:
                self._set_test_label(tr("models_empty"))
        except Exception as exc:
            self._set_test_label(tr("models_unavailable") +
                                 truncate(human_error(exc), 140))
        finally:
            self._models_busy = False


def open_settings_for(ctx, smgr, config, pid):
    """Run the settings dialog modally; returns True if saved."""
    dlg = SettingsDialog(ctx, smgr, config, pid)
    toolkit = smgr.createInstance("com.sun.star.awt.ExtToolkit")
    dlg.dialog.createPeer(toolkit, None)
    try:
        area = toolkit.getDesktopArea()
        win = dlg.dialog.getPeer()
        ps = win.getPosSize()
        win.setPosSize(max(0, (area.Width - ps.Width) // 2),
                       max(0, (area.Height - ps.Height) // 2),
                       ps.Width, ps.Height, 15)
    except Exception:
        pass
    dlg.dialog.execute()
    dlg.dialog.dispose()
    return dlg.saved
