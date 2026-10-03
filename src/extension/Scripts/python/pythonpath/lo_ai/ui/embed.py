# -*- coding: utf-8 -*-
"""Embedded assistant UI for the LibreOffice sidebar (lo_ai.ui.embed).

The panel window is created the officially supported way:
    ContainerWindowProvider.createContainerWindow(xdl_url, "", parent, None)
which returns a live dialog control container parented into the sidebar
panel. Controls are accessed by name via root.getControl(name); the root
window is resized from XSidebarPanel.getHeightForWidth().
"""

import threading

from .. import assistant as _assistant
from .. import document_bridge as _doc
from ..i18n import tr
from ..util import human_error, truncate
from .dialog_util import (XActionListener, XItemListener, XWindowListener,
                          MainThreadPump, string_seq)

try:
    import uno
    import unohelper
except Exception:
    uno = None
    unohelper = object

_POSIZE_ALL = 15  # X|Y|WIDTH|HEIGHT
EXTENSION_ID = "org.sphaera.lo.assistant"


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


class _ContextHandler(unohelper.Base, XItemListener):
    def __init__(self, view):
        self.view = view

    def itemStateChanged(self, *args):
        try:
            state = self.view.ctl("chkContext").getState()
            self.view.config.data["include_context"] = bool(state)
            self.view.config.save()
        except Exception:
            pass

    def disposing(self, *args):
        pass


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
            self.view.relayout(event.Width, event.Height)
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

    MARGIN = 6
    STATUS_H = 14
    BTN_H = 20
    INPUT_H = 48

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
        self._current_action = "chat"
        self.pump = MainThreadPump(smgr)
        self._build()
        try:
            self.parent.addWindowListener(_ParentResizeHandler(self))
        except Exception:
            pass

    # --- construction -------------------------------------------------------
    def _build(self):
        provider = self.smgr.createInstanceWithContext(
            "com.sun.star.awt.ContainerWindowProvider", self.ctx)
        xdl_url = self._extension_url() + "/Dialogs/AIChat.xdl"
        # Returns a live dialog control container parented into the sidebar.
        self.root = provider.createContainerWindow(xdl_url, "", self.parent, None)
        if self.root is None:
            raise RuntimeError("ContainerWindowProvider returned no window")

        self._fill_provider_combo()
        self._fill_model_combo()
        self._fill_action_combo()

        for name, handler in (("btnSend", _SendHandler(self)),
                              ("btnStop", _StopHandler(self)),
                              ("btnInsert", _ApplyHandler(self, "insert")),
                              ("btnReplace", _ApplyHandler(self, "replace")),
                              ("btnCopy", _CopyHandler(self)),
                              ("btnSettings", _SettingsHandler(self))):
            self.ctl(name).addActionListener(handler)
        self.ctl("chkContext").addItemListener(_ContextHandler(self))
        self.ctl("cmbProvider").addItemListener(_ProviderHandler(self))

        try:
            self.ctl("txtLang").setText(_assistant.DEFAULT_TARGET_LANG)
            self.ctl("cmbAction").setText(_assistant.action_label("chat"))
            self.ctl("cmbModel").setText(self.config.provider_settings(
                self._current_pid()).get("model", ""))
            self.ctl("lblStatus").setText(tr("ready"))
        except Exception:
            pass

    def _extension_url(self):
        pip = self.ctx.getValueByName(
            "/singletons/com.sun.star.deployment.PackageInformationProvider")
        return pip.getPackageLocation(EXTENSION_ID)

    def ctl(self, name):
        return self.root.getControl(name)

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
        return self._pid_for_label(self.ctl("cmbProvider").getText()) \
            or self.config.active_provider

    def _settings(self):
        return self.config.provider_settings(self._current_pid())

    def _fill_provider_combo(self):
        try:
            self.ctl("cmbProvider").getModel().setPropertyValue(
                "StringItemList",
                string_seq([l for _p, l in self._preset_labels()]))
            self.ctl("cmbProvider").setText(
                self._label_for_pid(self.config.active_provider))
        except Exception:
            pass

    def _fill_model_combo(self):
        try:
            from ..providers import get_preset
            pid = self._current_pid()
            models = list(get_preset(pid).get("models", []))
            saved = self.config.provider_settings(pid).get("model", "")
            if saved and saved not in models:
                models.insert(0, saved)
            self.ctl("cmbModel").getModel().setPropertyValue(
                "StringItemList", string_seq(models))
            self.ctl("cmbModel").setText(saved)
        except Exception:
            pass

    def _fill_action_combo(self):
        try:
            self.ctl("cmbAction").getModel().setPropertyValue(
                "StringItemList", string_seq(_assistant.action_labels()))
            self.ctl("cmbAction").setText(_assistant.action_label("chat"))
        except Exception:
            pass

    # --- layout ---------------------------------------------------------------
    def relayout(self, width, height):
        if not width or not height:
            return
        try:
            self.root.setPosSize(0, 0, width, height, _POSIZE_ALL)
        except Exception:
            pass
        M = self.MARGIN
        w = width

        def place(name, x, y, cw, ch):
            try:
                self.ctl(name).setPosSize(x, y, cw, ch, _POSIZE_ALL)
            except Exception:
                pass

        place("cmbProvider", M, 2, 150, 20)
        place("cmbModel", M + 154, 2, max(50, w - M * 2 - 154 - 28), 20)
        place("btnSettings", w - M - 26, 2, 26, 20)
        place("chkContext", M, 26, min(250, w - M * 2), 16)

        chat_y = 46
        bottom = height - M
        status_h = self.STATUS_H
        btn_y = bottom - status_h - self.BTN_H
        input_y = btn_y - M - self.INPUT_H
        chat_h = input_y - M - chat_y
        place("txtChat", M, chat_y, w - M * 2, max(40, chat_h))
        place("txtInput", M, input_y, w - M * 2, self.INPUT_H)
        bw = (w - M * 2 - M) // 3
        place("btnSend", M, btn_y, bw, self.BTN_H)
        place("btnStop", M + bw + M, btn_y, bw, self.BTN_H)
        place("btnInsert", M + (bw + M) * 2, btn_y,
              w - M * 2 - (bw + M) * 2, self.BTN_H)
        place("btnReplace", M, btn_y - self.BTN_H - 2, bw, self.BTN_H)
        place("btnCopy", M + bw + M, btn_y - self.BTN_H - 2, bw, self.BTN_H)
        place("lblStatus", M, bottom - status_h + 2, w - M * 2, status_h)

    def getHeightForWidth(self, n_width):
        """XSidebarPanel layout hook: fit to the given column width."""
        try:
            rect = self.parent.getPosSize()
            height = rect.Height if rect.Height > 0 else 400
        except Exception:
            height = 400
        try:
            self.relayout(n_width, height)
        except Exception:
            pass
        import uno
        ls = uno.createUnoStruct("com.sun.star.ui.LayoutSize")
        ls.MinimumWidth = 220
        ls.MinimumHeight = -1
        ls.MaximumHeight = 400
        return ls

    def getMinimalWidth(self):
        return 220

    # --- helpers -------------------------------------------------------------
    def set_status(self, text):
        try:
            self.ctl("lblStatus").setText(text)
        except Exception:
            pass

    def _chat_append(self, text):
        try:
            chat = self.ctl("txtChat")
            new = chat.getText() + text
            chat.setText(new)
            import uno
            sel = uno.createUnoStruct("com.sun.star.awt.Selection")
            sel.Min = len(new)
            sel.Max = len(new)
            chat.setSelection(sel)
        except Exception:
            pass

    def _enable_apply(self, enabled):
        for name in ("btnInsert", "btnReplace", "btnCopy"):
            try:
                self.ctl(name).getModel().setPropertyValue("Enabled", enabled)
            except Exception:
                pass

    # --- events -----------------------------------------------------------------
    def on_provider_changed(self):
        try:
            from ..providers import get_preset
            pid = self._current_pid()
            models = list(get_preset(pid).get("models", []))
            saved = self.config.provider_settings(pid).get("model", "")
            if saved and saved not in models:
                models.insert(0, saved)
            self.ctl("cmbModel").getModel().setPropertyValue(
                "StringItemList", string_seq(models))
            self.ctl("cmbModel").setText(saved)
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
        user_text = self.ctl("txtInput").getText().strip()
        action_key = _assistant.action_key_by_label(
            self.ctl("cmbAction").getText())
        if action_key == "chat" and not user_text:
            self.set_status(tr("type_first"))
            return

        pid = self._current_pid()
        settings = dict(self.config.provider_settings(pid))
        settings["model"] = self.ctl("cmbModel").getText().strip()
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
            action_key, user_text, context_block,
            _assistant.DEFAULT_TARGET_LANG)
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
            state = self.view.ctl("chkContext").getState()
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
