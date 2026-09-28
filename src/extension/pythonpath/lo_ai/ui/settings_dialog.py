"""Settings dialog: provider preset, endpoint, model, key, generation knobs."""

import threading

from ..util import human_error, truncate
from .dialog_util import (XActionListener, XItemListener, add_control,
                          make_dialog)

try:
    import unohelper
except Exception:  # outside LibreOffice: keep importable for tooling
    class unohelper(object):
        class Base(object):
            pass


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


class SettingsDialog(object):
    WIDTH = 520
    HEIGHT = 476

    def __init__(self, ctx, smgr, config, pid):
        self.ctx = ctx
        self.smgr = smgr
        self.config = config
        self.pid = pid or config.active_provider
        self.saved = False
        self._build()

    def _build(self):
        from ..providers import preset_labels
        W = self.WIDTH

        self.dialog, m = make_dialog(self.smgr, "AI Assistant — Settings", W, self.HEIGHT)

        add_control(m, "FixedText", "lblPreset", {"Label": "Preset:"}, 8, 9, 90, 12)
        labels = tuple(label for _p, label in preset_labels())
        add_control(m, "ComboBox", "cmbPreset",
                    {"Dropdown": True, "StringItemList": labels,
                     "Text": self._label_for_pid(self.pid)},
                    100, 6, W - 110, 12)

        self.lblNote = add_control(m, "FixedText", "lblNote", {"Label": "", "MultiLine": True},
                                   100, 20, W - 110, 22)

        add_control(m, "FixedText", "lblUrl", {"Label": "Base URL:"}, 8, 48, 90, 12)
        add_control(m, "Edit", "txtUrl", {"Text": ""}, 100, 45, W - 110, 12)

        add_control(m, "FixedText", "lblStyle", {"Label": "API style:"}, 8, 68, 90, 12)
        add_control(m, "ComboBox", "cmbStyle",
                    {"Dropdown": True,
                     "StringItemList": ("openai", "responses", "anthropic")},
                    100, 65, 120, 12)

        add_control(m, "FixedText", "lblModel", {"Label": "Model:"}, 8, 88, 90, 12)
        add_control(m, "ComboBox", "cmbModel", {"Dropdown": True},
                    100, 85, W - 110, 12)

        add_control(m, "FixedText", "lblKey", {"Label": "API key:"}, 8, 108, 90, 12)
        add_control(m, "Edit", "txtKey", {"EchoChar": 42}, 100, 105, W - 110, 12)
        add_control(m, "FixedText", "lblKeyHint",
                    {"Label": "Stored locally in the config file. Get a key at the provider's site.",
                     "MultiLine": True},
                    100, 119, W - 110, 16)

        add_control(m, "FixedText", "lblTemp", {"Label": "Temperature:"}, 8, 142, 90, 12)
        add_control(m, "Edit", "txtTemp", {"Text": ""}, 100, 139, 60, 12)
        add_control(m, "FixedText", "lblTempHint",
                    {"Label": "blank = don't send (required for o*/gpt-5 reasoning models)"},
                    166, 142, W - 174, 12)

        add_control(m, "FixedText", "lblMax", {"Label": "Max tokens:"}, 8, 162, 90, 12)
        add_control(m, "Edit", "txtMax", {"Text": ""}, 100, 159, 60, 12)
        add_control(m, "FixedText", "lblMaxHint", {"Label": "0/blank = provider default"},
                    166, 162, W - 174, 12)

        add_control(m, "FixedText", "lblTimeout", {"Label": "Timeout, s:"}, 8, 182, 90, 12)
        add_control(m, "Edit", "txtTimeout", {"Text": "180"}, 100, 179, 60, 12)

        add_control(m, "CheckBox", "chkStream",
                    {"Label": "Stream answers (typewriter effect)",
                     "State": 1},
                    8, 202, 280, 10)

        add_control(m, "FixedText", "lblSys", {"Label": "System prompt:"}, 8, 220, 200, 12)
        add_control(m, "Edit", "txtSys",
                    {"MultiLine": True, "VScroll": True},
                    8, 234, W - 16, 120)

        self.lblTest = add_control(m, "FixedText", "lblTest", {"Label": ""}, 8, 360, W - 16, 14)
        add_control(m, "Button", "btnTest", {"Label": "Test connection"}, 8, 378, 100, 16)

        add_control(m, "Button", "btnSave", {"Label": "Save", "Default": True},
                    W - 214, 378, 100, 16)
        add_control(m, "Button", "btnCancel", {"Label": "Cancel"}, W - 108, 378, 100, 16)

        self.dialog.getControl("btnSave").addActionListener(_SaveHandler(self))
        self.dialog.getControl("btnCancel").addActionListener(_CancelHandler(self))
        self.dialog.getControl("btnTest").addActionListener(_TestHandler(self))
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

    def _load_pid(self, pid):
        from ..providers import get_preset
        self.pid = pid
        preset = get_preset(pid)
        settings = self.config.provider_settings(pid)
        self.dialog.getControl("lblNote").setPropertyValue("Label", preset.get("note") or "")
        base = settings.get("base_url") or preset.get("base_url") or ""
        self.dialog.getControl("txtUrl").setText(base)
        self.dialog.getControl("cmbStyle").setText(settings.get("api_style") or preset["api_style"])
        models = list(preset.get("models", []))
        if settings.get("model") and settings["model"] not in models:
            models.insert(0, settings["model"])
        self.dialog.getControl("cmbModel").getModel().setPropertyValue(
            "StringItemList", tuple(models))
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
            "model": self._ctl_text("cmbModel").getText().strip(),
            "api_key": self._ctl_text("txtKey").getText().strip(),
            "temperature": self.config.coerce_float_none(self._ctl_text("txtTemp")),
            "max_tokens": self.config.coerce_int(self._ctl_text("txtMax"), 0),
            "timeout": timeout if timeout > 0 else 180,
            "streaming": bool(self.dialog.getControl("chkStream").getState()),
            "system_prompt": self._ctl_text("txtSys"),
        }

    def on_save(self):
        pid, settings = self._collect()
        if not settings["base_url"]:
            self.lblTest.setPropertyValue("Label", "Base URL is required.")
            return
        self.config.set_provider_settings(pid, settings)
        self.config.active_provider = pid
        self.config.save()
        self.saved = True
        self.pid = pid
        self.dialog.endDialog(1)

    def on_cancel(self):
        self.dialog.endDialog(0)

    def on_test(self):
        pid, settings = self._collect()
        self.lblTest.setPropertyValue("Label", "Testing %s…" % (settings["model"] or pid))
        worker = threading.Thread(target=self._test_worker, args=(settings,))
        worker.daemon = True
        worker.start()

    def _test_worker(self, settings):
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
            msg = "Connected. Model answered: %s" % truncate((answer or "").strip(), 60)
        except Exception as exc:
            ok = False
            msg = "Failed: %s" % truncate(human_error(exc), 140)
        try:
            self.lblTest.setPropertyValue(
                "Label", ("OK · " if ok else "FAIL · ") + msg)
        except Exception:
            pass


def open_settings_for(ctx, smgr, config, pid):
    """Run the settings dialog modally; returns True if saved."""
    dlg = SettingsDialog(ctx, smgr, config, pid)
    toolkit = smgr.createInstance("com.sun.star.awt.ExtToolkit")
    dlg.dialog.createPeer(toolkit, None)
    dlg.dialog.execute()
    dlg.dialog.dispose()
    return dlg.saved
