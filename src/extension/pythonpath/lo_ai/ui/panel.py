"""Main assistant panel: a modeless dialog usable in every LibreOffice module."""

import threading

from .. import assistant as _assistant
from .. import document_bridge as _doc
from ..util import human_error, truncate
from .dialog_util import (XActionListener, XItemListener, MainThreadPump,
                          add_control, make_dialog, make_selection)

try:
    import unohelper
except Exception:  # outside LibreOffice: keep importable for tooling
    class unohelper(object):
        class Base(object):
            pass


# --- listener adapters (pyuno requires one object per callback interface) ---

class _SendHandler(unohelper.Base, XActionListener):
    def __init__(self, panel):
        self.panel = panel

    def actionPerformed(self, *args):
        self.panel.on_send()


class _StopHandler(unohelper.Base, XActionListener):
    def __init__(self, panel):
        self.panel = panel

    def actionPerformed(self, *args):
        self.panel.on_stop()


class _ApplyHandler(unohelper.Base, XActionListener):
    def __init__(self, panel, mode):
        self.panel = panel
        self.mode = mode

    def actionPerformed(self, *args):
        self.panel.on_apply(self.mode)


class _CopyHandler(unohelper.Base, XActionListener):
    def __init__(self, panel):
        self.panel = panel

    def actionPerformed(self, *args):
        self.panel.on_copy()


class _SettingsHandler(unohelper.Base, XActionListener):
    def __init__(self, panel):
        self.panel = panel

    def actionPerformed(self, *args):
        self.panel.on_open_settings()


class _ContextHandler(unohelper.Base, XItemListener):
    def __init__(self, panel):
        self.panel = panel

    def itemStateChanged(self, *args):
        self.panel.on_context_toggled()

    def disposing(self, *args):
        pass


class _ProviderHandler(unohelper.Base, XItemListener):
    def __init__(self, panel):
        self.panel = panel

    def itemStateChanged(self, *args):
        self.panel.on_provider_changed()

    def disposing(self, *args):
        pass


# --- clipboard --------------------------------------------------------------

_TRANSFERABLE_CLASS = None


def _string_transferable(text):
    global _TRANSFERABLE_CLASS
    if _TRANSFERABLE_CLASS is None:
        from com.sun.star.datatransfer import XTransferable
        import uno

        class StringTransferable(unohelper.Base, XTransferable):
            def __init__(self, text):
                self.text = text
                self._flavor = uno.createUnoStruct(
                    "com.sun.star.datatransfer.DataFlavor")
                self._flavor.MimeType = "text/plain;charset=utf-16"
                self._flavor.HumanPresentableName = "Text"
                try:
                    self._flavor.DataType = uno.Type("string")
                except Exception:
                    pass

            def getTransferData(self, flavor):
                return self.text

            def getTransferDataFlavors(self):
                return (self._flavor,)

            def isDataFlavorSupported(self, flavor):
                return str(flavor.MimeType).startswith("text/plain")

        _TRANSFERABLE_CLASS = StringTransferable
    return _TRANSFERABLE_CLASS(text)


# --- panel -------------------------------------------------------------------

class Panel(object):
    WIDTH = 500
    HEIGHT = 434

    def __init__(self, ctx, smgr, config):
        self.ctx = ctx
        self.smgr = smgr
        self.config = config
        self.history = []
        self.last_answer = ""
        self.busy = False
        self._cancel = threading.Event()
        self._streaming_text = []
        self._last_pid = None
        self._current_action = "chat"
        self._closed = False
        self.pump = MainThreadPump(smgr)
        self._build()

    # --- construction -------------------------------------------------------
    def _build(self):
        W = self.WIDTH
        self.dialog, m = make_dialog(self.smgr, "AI Assistant", W, self.HEIGHT)

        add_control(m, "FixedText", "lblProvider", {"Label": "Provider:"}, 6, 9, 40, 12)
        labels = tuple(label for _pid, label in self._preset_labels())
        add_control(m, "ComboBox", "cmbProvider",
                    {"Dropdown": True, "Text": self._label_for_pid(self.config.active_provider),
                     "StringItemList": labels},
                    48, 6, 180, 12)
        add_control(m, "ComboBox", "cmbModel",
                    {"Dropdown": True, "Text": self._settings().get("model", "")},
                    232, 6, 200, 12)
        add_control(m, "Button", "btnSettings", {"Label": "Settings…"},
                    438, 5, 56, 14)

        add_control(m, "CheckBox", "chkContext",
                    {"Label": "Include selected text / document context",
                     "State": 1 if self.config.data.get("include_context") else 0},
                    6, 24, 224, 10)
        add_control(m, "FixedText", "lblAction", {"Label": "Action:"}, 238, 25, 30, 10)
        action_labels = tuple(_assistant.ACTIONS[k][1] for k in _assistant.ACTION_ORDER)
        add_control(m, "ComboBox", "cmbAction",
                    {"Dropdown": True, "Text": _assistant.ACTIONS["chat"][1],
                     "StringItemList": action_labels},
                    270, 24, 132, 12)
        add_control(m, "Edit", "txtLang",
                    {"Text": _assistant.DEFAULT_TARGET_LANG,
                     "HelpText": "Target language for the Translate action"},
                    406, 24, 88, 12)

        add_control(m, "Edit", "txtChat",
                    {"MultiLine": True, "ReadOnly": True, "VScroll": True},
                    6, 42, W - 12, 250)

        add_control(m, "Edit", "txtInput", {"MultiLine": True, "VScroll": True},
                    6, 298, W - 100, 44)
        add_control(m, "Button", "btnSend", {"Label": "Send", "Default": True},
                    W - 90, 298, 84, 20)
        add_control(m, "Button", "btnStop", {"Label": "Stop", "Enabled": False},
                    W - 90, 322, 84, 20)

        self.lblStatus = add_control(m, "FixedText", "lblStatus", {"Label": "Ready."},
                                     6, 348, W - 250, 12)
        add_control(m, "Button", "btnInsert", {"Label": "Insert", "Enabled": False},
                    W - 238, 346, 60, 14)
        add_control(m, "Button", "btnReplace", {"Label": "Replace", "Enabled": False},
                    W - 174, 346, 60, 14)
        add_control(m, "Button", "btnCopy", {"Label": "Copy", "Enabled": False},
                    W - 110, 346, 60, 14)
        add_control(m, "FixedText", "lblHint",
                    {"Label": "Insert appends at the cursor; Replace overwrites the selection.",
                     "VerticalAlign": 1},
                    6, 366, W - 12, 10)

        self.dialog.getControl("btnSend").addActionListener(_SendHandler(self))
        self.dialog.getControl("btnStop").addActionListener(_StopHandler(self))
        self.dialog.getControl("btnInsert").addActionListener(_ApplyHandler(self, "insert"))
        self.dialog.getControl("btnReplace").addActionListener(_ApplyHandler(self, "replace"))
        self.dialog.getControl("btnCopy").addActionListener(_CopyHandler(self))
        self.dialog.getControl("btnSettings").addActionListener(_SettingsHandler(self))
        self.dialog.getControl("chkContext").addItemListener(_ContextHandler(self))
        self.dialog.getControl("cmbProvider").addItemListener(_ProviderHandler(self))

    def _preset_labels(self):
        from ..providers import preset_labels
        return preset_labels()

    def _label_for_pid(self, pid):
        for p, label in self._preset_labels():
            if p == pid:
                return label
        return self._preset_labels()[0][1]

    def _pid_for_label(self, label):
        for p, lab in self._preset_labels():
            if lab == label:
                return p
        return None

    def _settings(self):
        return self.config.provider_settings(self._current_pid())

    def _current_pid(self):
        text = self.dialog.getControl("cmbProvider").getText()
        pid = self._pid_for_label(text)
        return pid or self.config.active_provider

    # --- lifecycle -----------------------------------------------------------
    def show(self):
        toolkit = self.smgr.createInstance("com.sun.star.awt.ExtToolkit")
        self.dialog.createPeer(toolkit, None)
        self.dialog.setVisible(True)
        try:
            self.dialog.toFront()
        except Exception:
            pass

    def is_alive(self):
        try:
            self.dialog.getControl("btnSend")
            return not self._closed
        except Exception:
            return False

    def close(self):
        self._closed = True
        self._cancel.set()
        try:
            self.dialog.dispose()
        except Exception:
            pass

    # --- helpers ----------------------------------------------------------------
    def _set_busy(self, busy, note=""):
        self.busy = busy
        try:
            self.dialog.getControl("btnSend").getModel().setPropertyValue(
                "Enabled", not busy)
            self.dialog.getControl("btnStop").getModel().setPropertyValue(
                "Enabled", busy)
        except Exception:
            pass
        if note:
            self.set_status(note)

    def set_status(self, text):
        try:
            self.lblStatus.setPropertyValue("Label", text)
        except Exception:
            pass

    def _chat_append(self, text):
        try:
            chat = self.dialog.getControl("txtChat")
            current = chat.getText()
            new = current + text
            chat.setText(new)
            sel = make_selection(len(new), len(new))
            if sel is not None:
                chat.setSelection(sel)
        except Exception:
            pass

    # --- events ---------------------------------------------------------------
    def on_context_toggled(self):
        try:
            state = self.dialog.getControl("chkContext").getState()
            self.config.data["include_context"] = bool(state)
            self.config.save()
        except Exception:
            pass

    def on_provider_changed(self):
        pid = self._current_pid()
        if pid == self._last_pid:
            return
        self._last_pid = pid
        settings = self.config.provider_settings(pid)
        try:
            from ..providers import get_preset
            models = list(get_preset(pid).get("models", []))
            if settings.get("model") and settings["model"] not in models:
                models.insert(0, settings["model"])
            self.dialog.getControl("cmbModel").getModel().setPropertyValue(
                "StringItemList", tuple(models))
            self.dialog.getControl("cmbModel").setText(settings.get("model", ""))
        except Exception:
            pass
        self.config.active_provider = pid
        try:
            self.config.save()
        except Exception:
            pass
        from ..providers import get_preset
        note = get_preset(pid).get("note") or ""
        self.set_status((settings.get("model") or "Set model in Settings…") +
                        ((" · " + note) if note else "")[:170])

    def on_open_settings(self):
        from .settings_dialog import open_settings_for
        open_settings_for(self.ctx, self.smgr, self.config, self._current_pid())
        self.on_provider_changed()

    def on_stop(self):
        self._cancel.set()

    def on_send(self):
        if self.busy:
            return
        user_text = self.dialog.getControl("txtInput").getText().strip()
        action_label = self.dialog.getControl("cmbAction").getText()
        action_key = "chat"
        for key, (label_, _t) in _assistant.ACTIONS.items():
            if label_ == action_label:
                action_key = key
                break

        if action_key == "chat" and not user_text:
            self.set_status("Type a message first.")
            return

        pid = self._current_pid()
        settings = dict(self.config.provider_settings(pid))
        settings["model"] = self.dialog.getControl("cmbModel").getText().strip()
        if not settings["model"]:
            self.set_status("Choose a model in Settings…")
            return
        self.config.set_provider_settings(pid, settings)
        self.config.active_provider = pid
        try:
            self.config.save()
        except Exception:
            pass

        target_lang = self.dialog.getControl("txtLang").getText().strip() or \
            _assistant.DEFAULT_TARGET_LANG

        context_block = ""
        if self.config.data.get("include_context"):
            try:
                desktop = self.smgr.createInstance("com.sun.star.frame.Desktop")
                model = desktop.getCurrentComponent()
                doc_ctx = _doc.collect_context(model)
                limit = int(self.config.data.get("context_chars") or 6000)
                context_block = _doc.context_prompt_block(doc_ctx, limit)
            except Exception:
                context_block = ""

        user_message = _assistant.build_user_message(
            action_key, user_text, context_block, target_lang)
        messages = _assistant.build_messages(
            settings.get("system_prompt") or None, self.history, user_message)

        self._current_action = action_key
        if action_key == "chat":
            self.history.append({"role": "user", "content": user_message})
            max_turns = int(self.config.data.get("history_messages") or 8)
            if len(self.history) > max_turns * 2:
                self.history = self.history[-(max_turns * 2):]

        self._chat_append("You: %s\n" % (user_text or action_label))
        self._streaming_text = []
        self._cancel = threading.Event()
        self._set_busy(True, "%s · %s …" % (settings.get("model"), pid))

        worker = threading.Thread(target=self._worker, args=(settings, messages))
        worker.daemon = True
        worker.start()

    def _worker(self, settings, messages):
        def on_delta(chunk):
            self._streaming_text.append(chunk)
            self.pump.schedule(self._flush_stream)

        try:
            from ..providers import create_provider
            provider = create_provider(settings)
            answer = provider.stream_chat(messages, on_delta, cancel=self._cancel)
        except Exception as exc:
            err = human_error(exc)
            self.pump.schedule(lambda: self._finish_error(err))
            return
        self.pump.schedule(lambda: self._finish_ok(answer))

    def _flush_stream(self):
        if not self._streaming_text:
            return
        chunk = "".join(self._streaming_text)
        self._streaming_text = []
        self._chat_append(chunk)

    def _remember_assistant(self, answer):
        if self._current_action == "chat":
            self.history.append({"role": "assistant", "content": answer})

    def _finish_ok(self, answer):
        self._flush_stream()
        if self._cancel.is_set():
            self._chat_append("\n[stopped]\n")
        self._chat_append("\n\n")
        self.last_answer = answer or ""
        self._remember_assistant(self.last_answer)
        self._set_busy(False, "Done · %d chars" % len(self.last_answer))
        self._enable_apply(len(self.last_answer) > 0)

    def _finish_error(self, message):
        self._chat_append("\n[error] %s\n\n" % message)
        self._set_busy(False, "Error: %s" % truncate(message, 120))
        self._enable_apply(False)

    def _enable_apply(self, enabled):
        for name in ("btnInsert", "btnReplace", "btnCopy"):
            try:
                self.dialog.getControl(name).getModel().setPropertyValue(
                    "Enabled", enabled)
            except Exception:
                pass

    def on_apply(self, mode):
        if not self.last_answer:
            return
        try:
            desktop = self.smgr.createInstance("com.sun.star.frame.Desktop")
            model = desktop.getCurrentComponent()
            ok = _doc.apply_text(model, self.last_answer, mode)
            self.set_status("Inserted." if ok else "Cannot insert here — use Copy.")
        except Exception as exc:
            self.set_status("Insert failed: %s" % truncate(human_error(exc), 100))

    def on_copy(self):
        if not self.last_answer:
            return
        try:
            clipboard = self.smgr.createInstance(
                "com.sun.star.datatransfer.clipboard.SystemClipboard")
            clipboard.setContents(_string_transferable(self.last_answer), None)
            self.set_status("Copied to clipboard.")
        except Exception as exc:
            self.set_status("Copy failed: %s" % truncate(human_error(exc), 100))


# --- module-level panel management -------------------------------------------

_PANEL = None


def show_panel(ctx, smgr, config):
    """Open (or focus) the assistant panel."""
    global _PANEL
    if _PANEL is not None and _PANEL.is_alive():
        try:
            _PANEL.dialog.toFront()
            return _PANEL
        except Exception:
            _PANEL = None
    _PANEL = Panel(ctx, smgr, config)
    _PANEL.show()
    return _PANEL
