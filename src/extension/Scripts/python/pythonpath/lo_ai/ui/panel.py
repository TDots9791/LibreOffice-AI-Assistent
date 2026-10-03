"""Main assistant panel: a modeless dialog usable in every LibreOffice module.

Side mode: the dialog is placed exactly over LibreOffice's own sidebar
column (right edge), so the document stays fully visible while the panel
is open. A background "glue" loop re-anchors the panel when the LibreOffice
window moves or resizes.
"""

import threading

from .. import assistant as _assistant
from .. import document_bridge as _doc
from ..i18n import tr
from ..util import human_error, truncate
from .dialog_util import (XActionListener, XItemListener,
                          XTopWindowListener,
                          XWindowListener, MainThreadPump, add_control,
                          make_dialog, make_selection, string_seq)

try:
    import unohelper
except Exception:
    class unohelper(object):
        class Base(object):
            pass


# --- listener adapters (pyuno requires one object per callback interface) -----

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


class _CloseHandler(unohelper.Base, XTopWindowListener):
    """Closes the modeless panel when the user clicks the window X."""

    def __init__(self, panel):
        self.panel = panel

    def windowClosing(self, *args):
        self.panel.close()

    def windowOpened(self, *args):
        pass

    def windowClosed(self, *args):
        pass

    def windowMinimized(self, *args):
        pass

    def windowNormalized(self, *args):
        pass

    def windowMaximized(self, *args):
        pass

    def disposing(self, *args):
        pass


class _SelfResizeHandler(unohelper.Base, XWindowListener):
    def __init__(self, panel):
        self.panel = panel

    def windowResized(self, event):
        try:
            self.panel.on_self_resized(event.Width, event.Height)
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


# --- clipboard ----------------------------------------------------------------

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


# --- panel ---------------------------------------------------------------------

class Panel(object):
    WIDTH = 380            # ширина боковой панели, px
    HEIGHT = 368           # высота диалога, юниты (низ: поле 16px под хинт)
    TAB_STRIP_W = 56       # полоса вкладок sidebar у правого края
    TOP_OFFSET = 92        # меню + панели инструментов
    BOTTOM_OFFSET = 34     # строка состояния

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
        self._last_geometry = None
        self._glue_panel_w = None
        self._base_px = None   # {control_name: (x,y,w,h)} in pixels
        self._base_size = None
        self.pump = MainThreadPump(smgr)
        self._build()

    # --- construction -------------------------------------------------------
    def _build(self):
        W = self.WIDTH
        self.dialog, m = make_dialog(self.smgr, tr("title_panel"), W,
                                      self.HEIGHT, sizeable=True)

        add_control(m, "ComboBox", "cmbProvider",
                    {"Dropdown": True,
                     "Text": self._label_for_pid(self.config.active_provider),
                     "StringItemList": [label for _pid, label in self._preset_labels()]},
                    16, 16, 150, 12)
        add_control(m, "ComboBox", "cmbModel",
                    {"Dropdown": True, "Text": self._settings().get("model", "")},
                    170, 16, 112, 12)
        add_control(m, "Button", "btnSettings", {"Label": tr("settings_btn")},
                    286, 15, 78, 14)

        add_control(m, "CheckBox", "chkContext",
                    {"Label": tr("include_context"),
                     "State": 1 if self.config.data.get("include_context") else 0},
                    16, 34, 332, 10)
        add_control(m, "ComboBox", "cmbAction",
                    {"Dropdown": True, "Text": _assistant.action_label("chat"),
                     "StringItemList": _assistant.action_labels()},
                    16, 48, 220, 12)
        add_control(m, "Edit", "txtLang",
                    {"Text": _assistant.DEFAULT_TARGET_LANG,
                     "HelpText": tr("act_translate")},
                    240, 48, 124, 12)

        add_control(m, "Edit", "txtChat",
                    {"MultiLine": True, "ReadOnly": True, "VScroll": True},
                    16, 64, W - 32, 206)

        add_control(m, "Edit", "txtInput", {"MultiLine": True, "VScroll": True},
                    16, 276, W - 112, 44)
        add_control(m, "Button", "btnSend", {"Label": tr("send")}, 292, 276, 72, 20)
        add_control(m, "Button", "btnStop", {"Label": tr("stop"), "Enabled": False},
                    292, 300, 72, 20)

        self.lblStatus = add_control(m, "FixedText", "lblStatus", {"Label": tr("ready")},
                                     16, 326, 130, 12)
        add_control(m, "Button", "btnInsert", {"Label": tr("insert"), "Enabled": False},
                    150, 324, 64, 14)
        add_control(m, "Button", "btnReplace", {"Label": tr("replace"), "Enabled": False},
                    218, 324, 64, 14)
        add_control(m, "Button", "btnCopy", {"Label": tr("copy"), "Enabled": False},
                    286, 324, 78, 14)
        add_control(m, "FixedText", "lblHint", {"Label": tr("hint_resize")},
                    16, 342, W - 32, 10)

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

    # --- lifecycle ------------------------------------------------------------
    def show(self):
        toolkit = self.smgr.createInstance("com.sun.star.awt.ExtToolkit")
        self.dialog.createPeer(toolkit, None)
        self._init_after_peer()
        self._capture_base_px()
        self._apply_saved_size()
        self._place_over_sidebar()
        self.dialog.setVisible(True)
        self._hook_resize()
        self._hook_close()
        self._start_glue()
        self._log_line("show ok, pump=%s, native sizeable" %
                       getattr(self.pump, "_mode", "?"))
        self.set_status(tr("ready"))

    def _win(self):
        """XWindow панели: getWindow() у диалога нет (XControl его не объявляет);
        peer-объект (VCLXDialog) реализует XWindow2 → XWindow."""
        return self.dialog.getPeer()

    def _capture_base_px(self):
        """Запомнить пиксельную геометрию контролов (база для релайаута)."""
        self._base_px = {}
        try:
            for name in ("cmbProvider", "cmbModel", "btnSettings",
                         "chkContext", "cmbAction", "txtLang", "txtChat",
                         "txtInput", "btnSend", "btnStop", "btnInsert",
                         "btnReplace", "btnCopy", "lblStatus", "lblHint"):
                ps = self.ctl_px(name).getPosSize()
                self._base_px[name] = (ps.X, ps.Y, ps.Width, ps.Height)
            ps = self._win().getPosSize()
            self._base_size = (ps.Width, ps.Height)
        except Exception:
            self._base_px = None

    def ctl_px(self, name):
        return self.dialog.getControl(name).getPeer()

    # Кнопки имеют ФИКСИРОВАННЫЙ размер и прижаты к правому/нижнему краю:
    # надписи не режутся ни при каком масштабе окна; тянется только содержимое
    # (комбобокс модели, чекбокс, действие, чат, ввод, статус, подсказка).
    _FIXED_TOP = ("btnSettings",)
    _FIXED_BOTTOM = ("btnSend", "btnStop", "btnInsert", "btnReplace", "btnCopy")

    def _relayout_to(self, width, height):
        """Разложить контролы под новый размер окна (width/height в px)."""
        if not self._base_px or not self._base_size:
            return
        w0, h0 = self._base_size
        b = self._base_px
        try:
            def place(name, x, y, w, h):
                self.ctl_px(name).setPosSize(int(x), int(y), int(w), int(h), 15)

            for name in self._FIXED_TOP:
                x0, y0, cw, ch = b[name]
                place(name, width - (w0 - x0 - cw), y0, cw, ch)
            for name in self._FIXED_BOTTOM:
                x0, y0, cw, ch = b[name]
                place(name, width - (w0 - x0 - cw), height - (h0 - y0), cw, ch)

            px, py, pw, ph = b["cmbProvider"]
            place("cmbProvider", px, py, pw, ph)
            sx, _sy, sw, sh = b["btnSettings"]
            mx, my, mw, mh = b["cmbModel"]
            place("cmbModel", mx, my,
                  max(60, width - (w0 - sx - sw) - 4 - mx), mh)

            cx, cy, cw2, ch2 = b["chkContext"]
            place("chkContext", cx, cy,
                  max(120, width - cx - (w0 - cx - cw2)), ch2)

            lx, ly, lw, lh = b["txtLang"]
            lang_x = width - (w0 - lx - lw)
            ax, _ay, _aw, ah = b["cmbAction"]
            place("cmbAction", ax, _ay, max(80, lang_x - 4 - ax), ah)
            place("txtLang", lang_x, ly, lw, lh)

            tx, ty, tw, _th = b["txtChat"]
            ix, iy, iw, ih = b["txtInput"]
            input_y = height - (h0 - iy)
            place("txtChat", tx, ty,
                  max(120, width - (w0 - tx - tw) - tx),
                  max(40, input_y - 4 - ty))
            place("txtInput", ix, input_y,
                  max(80, width - (w0 - ix - iw) - ix), ih)

            ins_x = width - (w0 - b["btnInsert"][0] - b["btnInsert"][2])
            stx, sty, _stw, sth = b["lblStatus"]
            place("lblStatus", stx, height - (h0 - sty),
                  max(60, ins_x - 4 - stx), sth)
            hx, hy, hw, hh = b["lblHint"]
            place("lblHint", hx, height - (h0 - hy),
                  max(100, width - (w0 - hx - hw) - hx), hh)
        except Exception:
            pass

    def _apply_saved_size(self):
        try:
            w = int(self.config.data.get("panel_width") or 0)
            h = int(self.config.data.get("panel_height") or 0)
            if w > 200 and h > 200:
                self._win().setPosSize(0, 0, w, h, 12)  # SIZE
        except Exception:
            pass

    def apply_window_prefs(self):
        """Вызывается из настроек: применить размер немедленно."""
        try:
            w = int(self.config.data.get("panel_width") or 0)
            h = int(self.config.data.get("panel_height") or 0)
            if w > 200 and h > 200:
                win = self._win()
                ps = win.getPosSize()
                win.setPosSize(ps.X, ps.Y, w, h, 15)
        except Exception:
            pass

    def _hook_resize(self):
        try:
            self._win().addWindowListener(_SelfResizeHandler(self))
        except Exception:
            pass

    def on_self_resized(self, width, height):
        """Ресайз делает оконный менеджер (нативный WB_SIZEABLE); здесь —
        минимальный размер, перекладка контролов и отложенное сохранение."""
        try:
            ps = self._win().getPosSize()
            w, h = ps.Width, ps.Height
            if w < self.MIN_W or h < self.MIN_H:
                w, h = max(self.MIN_W, w), max(self.MIN_H, h)
                self._win().setPosSize(ps.X, ps.Y, w, h, 15)
        except Exception:
            w, h = int(width), int(height)
        self._relayout_to(w, h)
        timer = getattr(self, "_save_timer", None)
        if timer is not None:
            try:
                timer.cancel()
            except Exception:
                pass
        self._save_timer = threading.Timer(0.8, self._schedule_save_size)
        self._save_timer.daemon = True
        self._save_timer.start()

    def _schedule_save_size(self):
        # из потока таймера UNO трогать нельзя — через pump в главный поток
        self.pump.schedule(self._save_size)

    def _save_size(self):
        try:
            ps = self._win().getPosSize()
            self.config.data["panel_width"] = ps.Width
            self.config.data["panel_height"] = ps.Height
            self.config.save()
        except Exception:
            pass

    def _init_after_peer(self):
        """Combo Text as a model property is unreliable; set on live controls."""
        try:
            self.on_provider_changed(force=True)
        except Exception:
            pass
        try:
            self.dialog.getControl("cmbAction").setText(
                _assistant.action_label("chat"))
        except Exception:
            pass

    # --- side placement ---------------------------------------------------------
    def _lo_geometry(self):
        """(frame_x, frame_y, frame_w, frame_h) окна LibreOffice или None."""
        try:
            desktop = self.smgr.createInstance("com.sun.star.frame.Desktop")
            model = desktop.getCurrentComponent()
            container = (model.getCurrentController()
                         .getFrame().getContainerWindow())
            ps = container.getPosSize()
            return (ps.X, ps.Y, ps.Width, ps.Height)
        except Exception:
            return None

    def _panel_rect(self, lo):
        fx, fy, fw, fh = lo
        # после ручного ресайза размер хранится в config (px); клей отслеживает
        # только позицию окна LibreOffice, не возвращая сохранённый размер
        w = int(self.config.data.get("panel_width") or 0)
        h = int(self.config.data.get("panel_height") or 0)
        if w > 200 and h > 200:
            panel_w = w
        else:
            panel_w = getattr(self, "_glue_panel_w", None) or min(
                self.WIDTH + 40, max(320, fw // 4))
            h = fh - self.TOP_OFFSET - self.BOTTOM_OFFSET
        x = fx + fw - panel_w - self.TAB_STRIP_W
        y = fy + self.TOP_OFFSET
        return (x, y, panel_w, h)

    def _place_over_sidebar(self):
        lo = self._lo_geometry()
        if not lo:
            self._log_line("place: no LO geometry")
            return
        rect = self._panel_rect(lo)
        self._glue_panel_w = rect[2]
        self._last_geometry = (lo, rect)
        try:
            self._win().setPosSize(*rect, 15)
            self._log_line("place ok: lo=%s rect=%s" % (lo, rect))
        except Exception as exc:
            self._log_line("place failed: %r lo=%s rect=%s" % (exc, lo, rect))

    def _start_glue(self):
        def glue_loop():
            import time
            while not self._closed:
                try:
                    self.pump.schedule(self._glue_step)
                except Exception:
                    pass
                time.sleep(0.4)
        worker = threading.Thread(target=glue_loop)
        worker.daemon = True
        worker.start()

    def _glue_step(self):
        if self._closed:
            return
        try:
            lo = self._lo_geometry()
            if not lo:
                if not getattr(self, "_glue_none_logged", False):
                    self._glue_none_logged = True
                    self._log_line("glue: no LO geometry")
                return
            rect = self._panel_rect(lo)
            key = (lo, rect)
            if key == self._last_geometry:
                return
            self._last_geometry = key
            self._glue_panel_w = rect[2]
            self._win().setPosSize(*rect, 15)
        except Exception:
            pass

    # --- минимальный размер окна (ресайз — нативный, через WM) -----------------
    MIN_W = 320
    MIN_H = 260

    def _log_line(self, text):
        """Проброс диагностики в error.log (для обработчиков мыши)."""
        try:
            import os
            from ..uno_env import default_config_dir
            directory = default_config_dir()
            os.makedirs(directory, exist_ok=True)
            stamp = __import__("datetime").datetime.now().strftime("%H:%M:%S")
            with open(os.path.join(directory, "error.log"), "a",
                      encoding="utf-8") as fh:
                fh.write("[%s] %s\n" % (stamp, text))
        except Exception:
            pass

    def _hook_close(self):
        closer = _CloseHandler(self)
        for target in (self.dialog, self.dialog.getPeer()):
            try:
                target.addTopWindowListener(closer)
                break
            except Exception:
                continue

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

    # --- helpers -----------------------------------------------------------------
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

    # --- events --------------------------------------------------------------------
    def on_context_toggled(self):
        try:
            state = self.dialog.getControl("chkContext").getState()
            self.config.data["include_context"] = bool(state)
            self.config.save()
        except Exception:
            pass

    def on_provider_changed(self, force=False):
        pid = self._current_pid()
        if pid == self._last_pid and not force:
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
        from ..providers import get_preset
        note = get_preset(pid).get("note") or ""
        self.set_status((settings.get("model") or tr("choose_model")) +
                        ((" · " + note) if note else "")[:170])

    def on_open_settings(self):
        from .settings_dialog import open_settings_for
        saved = open_settings_for(self.ctx, self.smgr, self.config,
                                  self._current_pid())
        if saved:
            self.set_status(tr("saved"))
            self.apply_window_prefs()
        self.on_provider_changed(force=True)

    def on_stop(self):
        self._cancel.set()

    def on_send(self):
        if self.busy:
            return
        user_text = self.dialog.getControl("txtInput").getText().strip()
        action_label_text = self.dialog.getControl("cmbAction").getText()
        action_key = _assistant.action_key_by_label(action_label_text)

        if action_key == "chat" and not user_text:
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

        # --- агентный режим: модель читает и правит живой документ -----------
        agent_mode = (action_key == "chat"
                      and bool(self.config.data.get("agent_enabled", True)))
        doc_model = doc_app = None
        provider = None
        if agent_mode:
            try:
                desktop = self.smgr.createInstance("com.sun.star.frame.Desktop")
                doc_model = desktop.getCurrentComponent()
                doc_app = _doc.detect_app(doc_model)
                agent_mode = doc_app in ("calc", "writer")
            except Exception:
                agent_mode = False
        if agent_mode:
            try:
                from ..providers import create_provider
                provider = create_provider(settings)
                agent_mode = bool(getattr(provider, "supports_tools", False))
            except Exception:
                agent_mode = False
        if agent_mode:
            self._current_action = "chat"
            self._chat_append("%s%s\n" % (tr("you"), user_text))
            self._streaming_text = []
            self._cancel = threading.Event()
            self._set_busy(True, "%s · agent …" % settings.get("model"))
            worker = threading.Thread(
                target=self._agent_worker,
                args=(doc_model, provider, user_text, list(self.history),
                      int(self.config.data.get("agent_max_steps") or 12),
                      doc_app))
            worker.daemon = True
            worker.start()
            return

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

        self._chat_append("%s%s\n" % (tr("you"), user_text or action_label_text))
        self._streaming_text = []
        self._cancel = threading.Event()
        self._set_busy(True, "%s …" % settings.get("model"))

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

    def _agent_worker(self, doc_model, provider, user_text, history,
                      max_steps, doc_app):
        """Агентный цикл: модель + инструменты над живым документом."""
        from ..agent import run_agent

        def on_step(label):
            self.pump.schedule(
                lambda: self._chat_append("⚙ %s\n" % label))

        try:
            answer = run_agent(doc_model, provider, user_text, history,
                               on_step, cancel=self._cancel,
                               max_steps=max_steps, app=doc_app,
                               run_on_main=lambda fn: self.pump.call(fn))
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
            self._chat_append(tr("stopped") + "\n")
        self._chat_append("\n\n")
        self.last_answer = answer or ""
        self._remember_assistant(self.last_answer)
        self._set_busy(False, tr("done") + "%d%s" % (len(self.last_answer),
                                                     tr("chars")))
        self._enable_apply(len(self.last_answer) > 0)

    def _finish_error(self, message):
        self._chat_append("\n[error] %s\n\n" % message)
        self._set_busy(False, tr("fail") + truncate(message, 120))
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
            self.set_status(tr("inserted") if ok else tr("cannot_insert"))
        except Exception as exc:
            self.set_status(tr("insert_failed") + truncate(human_error(exc), 100))

    def on_copy(self):
        if not self.last_answer:
            return
        try:
            clipboard = self.smgr.createInstance(
                "com.sun.star.datatransfer.clipboard.SystemClipboard")
            clipboard.setContents(_string_transferable(self.last_answer), None)
            self.set_status(tr("copied"))
        except Exception as exc:
            self.set_status(tr("copy_failed") + truncate(human_error(exc), 100))


# --- module-level panel management ----------------------------------------------

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
