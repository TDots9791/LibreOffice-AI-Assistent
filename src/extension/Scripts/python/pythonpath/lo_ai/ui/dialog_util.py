"""UNO dialog helpers and a main-thread callback pump (streaming-safe)."""

import threading
from collections import deque

try:
    import uno
    from com.sun.star.awt import XActionListener  # type: ignore
    from com.sun.star.awt import XItemListener  # type: ignore
    from com.sun.star.awt import XCallback  # type: ignore
    from com.sun.star.awt import XEventHandler  # type: ignore
    from com.sun.star.awt import XTopWindowListener  # type: ignore
except Exception:  # tooling outside LibreOffice: classes must still import
    uno = None
    XActionListener = XItemListener = object
    XCallback = XEventHandler = XTopWindowListener = object


def available():
    return uno is not None


def make_selection(start, end):
    """com.sun.star.awt.Selection struct without import-time UNO dependency."""
    try:
        sel = uno.createUnoStruct("com.sun.star.awt.Selection")
        sel.Min = start
        sel.Max = end
        return sel
    except Exception:
        return None


def make_dialog(smgr, title, width, height):
    model = smgr.createInstance("com.sun.star.awt.UnoControlDialogModel")
    model.setPropertyValue("Title", title)
    model.setPropertyValue("Width", width)
    model.setPropertyValue("Height", height)
    dialog = smgr.createInstance("com.sun.star.awt.UnoControlDialog")
    dialog.setModel(model)
    return dialog, model


def string_seq(values):
    """Type a python sequence as []string for UNO property sets."""
    if uno is not None:
        try:
            return uno.Any("[]string", tuple(str(v) for v in values))
        except Exception:
            pass
    return tuple(str(v) for v in values)


def add_control(dlg_model, kind, name, props, x, y, w, h):
    """kind e.g. 'Button', 'Edit', 'ComboBox', 'CheckBox', 'FixedText'."""
    ctl = dlg_model.createInstance("com.sun.star.awt.UnoControl%sModel" % kind)
    ctl.setPropertyValue("Name", name)
    for prop, value in (("PositionX", x), ("PositionY", y),
                        ("Width", w), ("Height", h)):
        ctl.setPropertyValue(prop, value)
    if props:
        info = ctl.getPropertySetInfo()
        for key, value in props.items():
            if info.hasPropertyByName(key):
                try:
                    if key == "StringItemList":
                        value = string_seq(value)
                    ctl.setPropertyValue(key, value)
                except Exception:
                    pass
    dlg_model.insertByName(name, ctl)
    return ctl


class MainThreadPump(object):
    """Runs callables on the UNO main thread.

    Primary strategy: com.sun.star.awt.AsyncCallback (one-shot callback per
    arming). Fallback: a polling com.sun.star.awt.Timer. Last resort:
    call directly from the worker thread.
    """

    def __init__(self, smgr):
        self._lock = threading.Lock()
        self._queue = deque()
        self._pending = False
        self._mode = "direct"
        self._async_cb = None
        try:
            self._async_cb = smgr.createInstance("com.sun.star.awt.AsyncCallback")
            self._mode = "async"
        except Exception:
            self._mode = "direct"
        self._timer = None
        if self._mode == "direct":
            try:
                self._timer = smgr.createInstance("com.sun.star.awt.Timer")
                self._timer.setHandler(self)
                self._timer.start(120, 120)
                self._mode = "timer"
            except Exception:
                self._mode = "direct"

    def schedule(self, fn):
        with self._lock:
            self._queue.append(fn)
            if self._pending:
                return
            self._pending = True
            mode = self._mode
        if mode == "direct":
            self._drain()
            return
        if mode == "timer":
            return  # already polling
        try:
            self._async_cb.addCallback(self)
        except Exception:
            with self._lock:
                self._mode = "direct"
            self._drain()

    # com.sun.star.awt.XCallback
    def notify(self, *args):
        try:
            self._async_cb.removeCallback(self)
        except Exception:
            pass
        self._drain()

    # com.sun.star.awt.XEventHandler (timer fallback)
    def handleEvent(self, *args):
        self._drain()
        return True

    def _drain(self):
        with self._lock:
            self._pending = False
            items = list(self._queue)
            self._queue.clear()
        for fn in items:
            try:
                fn()
            except Exception:
                pass
