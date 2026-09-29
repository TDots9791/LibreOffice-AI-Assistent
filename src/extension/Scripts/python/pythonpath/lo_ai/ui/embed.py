# -*- coding: utf-8 -*-
"""Embedded assistant UI for the LibreOffice sidebar (lo_ai.ui.embed).

Builds a compact chat panel as a UnoControlDialog whose peer lives on the
sidebar-provided parent window; relayouts on parent resize.
"""

import threading

from .. import assistant as _assistant
from .. import document_bridge as _doc
from ..i18n import tr
from ..util import human_error, truncate
from .dialog_util import (XActionListener, XItemListener, XWindowListener,
                          MainThreadPump, add_control, make_dialog,
                          make_selection, string_seq)

try:
    import uno
    import unohelper
except Exception:
    uno = None
    unohelper = object

_POSIZE_ALL = 15  # X|Y|WIDTH|HEIGHT

try:
    from com.sun.star.awt import XTopWindowListener  # noqa: F401 (unused here)
except Exception:
    pass


class _SendHandler(unohelper.Base, XActionListener):
    def __init__(self, view):
        self.view = view

    def actionPerformed(self, *args):
        self.view.on_send()


class _StopHandler(unohelper.Base, XActionListener):
    def __init__(self, view):
        self.view = view

    def actionPerformed(self, *args):
        self.view.on_stop()


class _ApplyHandler(unohelper.Base, XActionListener):
    def __init__(self, view, mode):
        self.view = view
        self.mode = mode

    def actionPerformed(self, *args):
        self.view.on_apply(self.mode)


class _CopyHandler(unohelper.Base, XActionListener):
    def __init__(self, view):
        self.view = view

    def actionPerformed(self, *args):
        self.view.on_copy()


class _SettingsHandler(unohelper.Base, XActionListener):
    def __init__(self, view):
        self.view = view

    def actionPerformed(self, *args):
        self.view.on_open_settings()


class _ProviderHandler(unohelper.Base, XItemListener):
    def __init__(self, view):
        self.view = view

    def itemStateChanged(self, *args):
        self.view.on_provider_changed()

    def disposing(self, *args):
        pass


class _ParentResizeHandler(unohelper.Base, XWindowListener):
    def __init__(self, view):
        self.view = view

    def windowResized(self, event):
        try:
            rect = event.Source.getPosSize()
            self.view.relayout(rect.Width, rect.Height)
        except Exception:
            pass

    def windowMoved(self, *args):
        pass

    def windowShown(self, *args):
        pass

    def windowHidden(self, *args):
        pass

    def disposing(self, *args):
        pass


class EmbeddedPanel(object):
    """Compact assistant view embedded into a sidebar panel window."""

    ROW_TOP = 26
    ROW_INPUT = 56
    ROW_SEND = 24
    ROW_STATUS = 20
    MARGIN = 6

    def __init__(self, ctx, smgr, config, parent_window):
        self.ctx = ctx
        self.smgr = smgr
        self.config = config
        self.parent = parent_window
        self.history = []
        self.last_answer = ""
        self.busy = False
        self._cancel = threading.Event()
        self._streaming_text = []
        self._last_pid = None
        self.pump = MainThreadPump(smgr)
        self._build()
        self._hook_resize()

    # --- construction -------------------------------------------------------
    def _build(self):
        self.dialog, m = make_dialog(self.smgr, tr("title_panel"), 320, 600)

        add_control(m, "ComboBox", "cmbProvider",
                    {"Dropdown": True,
                     "Text": self._label_for_pid(self.config.active_provider),
                     "StringItemList": [l for _p, l in self._preset_labels()]},
                    4, 2, 140, 12)
        add_control(m, "ComboBox", "cmbModel",
                    {"Dropdown": True, "Text": self._settings().get("model", "")},
                    148, 2, 116, 12)
        add_control(m, "Button", "btnSettings", {"Label": "…"}, 268, 1, 24, 14)

        add_control(m, "CheckBox", "chkContext",
                    {"Label": tr("include_context"),
                     "State": 1 if self.config.data.get("include_context") else 0},
                    4, 16, 200, 10)

        add_control(m, "Edit", "txtChat",
                    {"MultiLine": True, "ReadOnly": True, "VScroll": True},
                    4, 30, 288, 380)

        add_control(m, "Edit", "txtInput", {"MultiLine": True, "VScroll": True},
                    4, 416, 288, 44)

        add_control(m, "Button", "btnSend", {"Label": tr("send")}, 4, 464, 90, 18)
        add_control(m, "Button", "btnStop", {"Label": tr("stop"), "Enabled": False},
                    98, 464, 70, 18)
        add_control(m, "Button", "btnInsert", {"Label": tr("insert"), "Enabled": False},
                    172, 464, 60, 18)
        add_control(m, "Button", "btnReplace", {"Label": tr("replace"), "Enabled": False},
                    236, 464, 70, 18)
        add_control(m, "Button", "btnCopy", {"Label": tr("copy"), "Enabled": False},
                    310, 464, 60, 18)

        self.lblStatus = add_control(m, "FixedText", "lblStatus",
                                     {"Label": tr("ready")}, 4, 486, 288, 12)

        for name, handler in (("btnSend", _SendHandler(self)),
                              ("btnStop", _StopHandler(self)),
                              ("btnInsert", _ApplyHandler(self, "insert")),
                              ("btnReplace", _ApplyHandler(self, "replace")),
                              ("btnCopy", _CopyHandler(self)),
                              ("btnSettings", _SettingsHandler(self))):
            self.dialog.getControl(name).addActionListener(handler)
        self.dialog.getControl("chkContext").addItemListener(
            _ProviderCtxHandler(self))
        self.dialog.getControl("cmbProvider").addItemListener(
            _ProviderHandler(self))

    def _hook_resize(self):
        try:
            self.parent.addWindowListener(_ParentResizeHandler(self))
        except Exception:
            pass
        try:
            ps = self.parent.getPosSize()
            self.relayout(ps.Width, ps.Height)
        except Exception:
            pass

    def relayout(self, width, height):
        """Pixel-position all controls to fit the sidebar panel size."""
        if not width or not height:
            return
        try:
            win = self.dialog.getWindow()
            win.setPosSize(0, 0, width, height, _POSIZE_ALL)
        except Exception:
            return
        M = self.MARGIN

        def place(name, x, y, w, h):
            try:
                self.dialog.getControl(name).getWindow().setPosSize(
                    x, y, w, h, _POSIZE_ALL)
            except Exception:
                pass

        place("cmbProvider", M, 2, 140, 20)
        place("cmbModel", M + 144, 2, max(60, width - M * 2 - 144 - 30), 20)
        place("btnSettings", width - M - 26, 2, 26, 20)
        place("chkContext", M, 26, min(240, width - M * 2), 16)

        chat_y = 46
        send_h = 22
        input_h = 52
        status_h = 16
        chat_h = height - chat_y - M - input_h - M - send_h - M - status_h - 4
        place("txtChat", M, chat_y, width - M * 2, max(60, chat_h))
        input_y = chat_y + max(60, chat_h) + M
        place("txtInput", M, input_y, width - M * 2, input_h)
        btn_y = input_y + input_h + M
        bw = (width - M * 2 - M * 3) // 4
        place("btnSend", M, btn_y, bw, send_h)
        place("btnStop", M + (bw + M), btn_y, bw, send_h)
        place("btnInsert", M + (bw + M) * 2, btn_y, bw, send_h)
        place("btnReplace", M + (bw + M) * 3, btn_y, max(40, bw - 10), send_h)
        place("btnCopy", width - M - max(40, bw - 10), btn_y, max(40, bw - 10), send_h)
        place("lblStatus", M, btn_y + send_h + 4, width - M * 2, status_h)

    # --- helpers -------------------------------------------------------------
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

    def _current_pid(self):
        return self._pid_for_label(self.dialog.getControl("cmbProvider").getText()) \
            or self.config.active_provider

    def _settings(self):
        return self.config.provider_settings(self._current_pid())

    def set_status(self, text):
        try:
            self.lblStatus.setPropertyValue("Label", text)
        except Exception:
            pass

    def _chat_append(self, text):
        try:
            chat = self.dialog.getControl("txtChat")
            new = chat.getText() + text
            chat.setText(new)
            sel = make_selection(len(new), len(new))
            if sel is not None:
                chat.setSelection(sel)
        except Exception:
            pass

    def _enable_apply(self, enabled):
        for name in ("btnInsert", "btnReplace", "btnCopy"):
            try:
                self.dialog.getControl(name).getModel().setPropertyValue(
                    "Enabled", enabled)
            except Exception:
                pass

    # --- events -----------------------------------------------------------------
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
                "StringItemList", string_seq(models))
            self.dialog.getControl("cmbModel").setText(settings.get("model", ""))
        except Exception:
            pass
        self.config.active_provider = pid
        try:
            self.config.save()
        except Exception:
            pass

    def on_open_settings(self):
        from .settings_dialog import open_settings_for
        saved = open_settings_for(self.ctx, self.smgr, self.config,
                                  self._current_pid())
        if saved:
            self.set_status(tr("saved"))
        self.on_provider_changed()

    def on_stop(self):
        self._cancel.set()

    def on_send(self):
        if self.busy:
            return
        user_text = self.dialog.getControl("txtInput").getText().strip()
        action_key = "chat"
        if not user_text:
            self.set_status(tr("type_first"))
            return

        pid = self._current_pid()
        settings = dict(self.config.provider_settings(pid))
        settings["model"] = self.dialog.getControl("cmbModel").getText().strip()
        if not settings["model"]:
            self.set_status(tr("choose_model"))
            return
        self.config.set_provider_settings(pid, settings)
        self.config.active_provider = pid
        try:
            self.config.save()
        except Exception:
            pass

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
            action_key, user_text, context_block, None)
        messages = _assistant.build_messages(
            settings.get("system_prompt") or None, self.history, user_message)

        self._current_action = action_key
        self.history.append({"role": "user", "content": user_message})
        max_turns = int(self.config.data.get("history_messages") or 8)
        if len(self.history) > max_turns * 2:
            self.history = self.history[-(max_turns * 2):]

        self._chat_append("%s%s\n" % (tr("you"), user_text))
        self._streaming_text = []
        self._cancel = threading.Event()
        self.busy = True
        self.set_status("%s …" % settings.get("model"))

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

    def _finish_ok(self, answer):
        self._flush_stream()
        if self._cancel.is_set():
            self._chat_append(tr("stopped") + "\n")
        self._chat_append("\n\n")
        self.last_answer = answer or ""
        if self._current_action == "chat":
            self.history.append({"role": "assistant", "content": self.last_answer})
        self.busy = False
        self.set_status(tr("done") + "%d%s" % (len(self.last_answer), tr("chars")))
        self._enable_apply(len(self.last_answer) > 0)

    def _finish_error(self, message):
        self._chat_append("\n[error] %s\n\n" % message)
        self.busy = False
        self.set_status(tr("fail") + truncate(message, 120))
        self._enable_apply(False)

    def on_apply(self, mode):
        if not self.last_answer:
            return
        try:
            desktop = self.smgr.createInstance("com.sun.star.frame.Desktop")
            model = desktop.getCurrentComponent()
            ok = _doc.apply_text(model, self.last_answer, mode)
            self.set_status(tr("inserted") if ok else tr("cannot_insert"))
        except Exception as exc:
            self.set_status(tr("insert_failed") + truncate(human_error(exc), 100))

    def on_copy(self):
        if not self.last_answer:
            return
        try:
            clipboard = self.smgr.createInstance(
                "com.sun.star.datatransfer.clipboard.SystemClipboard")
            clipboard.setContents(_make_transferable(self.last_answer), None)
            self.set_status(tr("copied"))
        except Exception as exc:
            self.set_status(tr("copy_failed") + truncate(human_error(exc), 100))


class _ProviderCtxHandler(unohelper.Base, XItemListener):
    def __init__(self, view):
        self.view = view

    def itemStateChanged(self, *args):
        try:
            state = self.view.dialog.getControl("chkContext").getState()
            self.view.config.data["include_context"] = bool(state)
            self.view.config.save()
        except Exception:
            pass

    def disposing(self, *args):
        pass


_TRANSFERABLE_CLASS = None


def _make_transferable(text):
    global _TRANSFERABLE_CLASS
    if _TRANSFERABLE_CLASS is None:
        from com.sun.star.datatransfer import XTransferable

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
