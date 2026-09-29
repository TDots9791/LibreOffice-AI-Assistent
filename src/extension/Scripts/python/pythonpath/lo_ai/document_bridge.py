"""UNO bridge: context extraction and text application for all LibreOffice modules.

Handles Writer, Calc, Impress and Draw. Unknown document types degrade
gracefully (chat + copy to clipboard still work).
"""

from .util import truncate

WRITER = "writer"
CALC = "calc"
IMPRESS = "impress"
DRAW = "draw"
OTHER = "other"

_SERVICE_MAP = {
    "com.sun.star.text.TextDocument": WRITER,
    "com.sun.star.sheet.SpreadsheetDocument": CALC,
    "com.sun.star.presentation.PresentationDocument": IMPRESS,
    "com.sun.star.drawing.DrawingDocument": DRAW,
}

_APP_TITLES = {
    WRITER: "Writer",
    CALC: "Calc",
    IMPRESS: "Impress",
    DRAW: "Draw",
    OTHER: "",
}


class DocContext(object):
    def __init__(self, app, selection_text="", description="", can_insert=False,
                 can_replace=False, model=None):
        self.app = app
        self.selection_text = selection_text
        self.description = description
        self.can_insert = can_insert
        self.can_replace = can_replace
        self.model = model  # XModel of the current component (not stored in config)


def detect_app(model):
    try:
        for service, app in _SERVICE_MAP.items():
            if model.supportsService(service):
                return app
    except Exception:
        pass
    return OTHER


def _writer_selection_text(controller):
    cursor = controller.ViewCursor
    try:
        return cursor.getString() or ""
    except Exception:
        return ""


def _writer_document_text(model, limit):
    try:
        text = model.getText().getString()
        return truncate(text, limit)
    except Exception:
        return ""


def _calc_selection_text(controller, limit):
    sel = controller.getSelection()
    if sel is None:
        return ""
    try:
        if sel.supportsService("com.sun.star.sheet.SheetCellRange") or \
           sel.supportsService("com.sun.star.sheet.SheetCellCursor"):
            rows = sel.getDataArray()
            lines = []
            for row in rows[:200]:
                lines.append(" | ".join(("%s" % v) for v in row))
            return truncate("\n".join(lines), limit)
    except Exception:
        pass
    try:
        return str(sel.getString())  # single cell
    except Exception:
        return ""


def _iter_selected_shapes(sel):
    """getSelection() in Draw/Impress is one shape (single) or XShapes (multi)."""
    shapes = []
    if sel is None:
        return shapes
    if hasattr(sel, "getByIndex") and hasattr(sel, "Count"):
        for i in range(min(sel.Count, 5)):
            shapes.append(sel.getByIndex(i))
    elif hasattr(sel, "getString"):
        shapes.append(sel)
    return shapes


def _draw_selection_text(controller, limit):
    try:
        sel = controller.getSelection()
    except Exception:
        return ""
    parts = []
    for shape in _iter_selected_shapes(sel):
        if hasattr(shape, "getString"):
            try:
                parts.append(shape.getString())
            except Exception:
                pass
    return truncate("\n\n".join(p for p in parts if p), limit)


def _current_page_text(controller, limit):
    try:
        page = controller.CurrentPage
        parts = []
        for i in range(page.Count):
            shape = page.getByIndex(i)
            try:
                if shape.supportsService("com.sun.star.presentation.TitleTextShape"):
                    parts.append(shape.getString())
            except Exception:
                pass
        return truncate("\n".join(parts), limit)
    except Exception:
        return ""


def collect_context(model, limit=6000):
    """Build a DocContext for whatever document is currently active."""
    if model is None:
        return DocContext(OTHER)
    app = detect_app(model)
    ctx = DocContext(app, model=model, can_insert=(app in (WRITER, CALC, IMPRESS, DRAW)),
                     can_replace=(app in (WRITER, CALC, IMPRESS, DRAW)))
    try:
        controller = model.getCurrentController()
    except Exception:
        controller = None
    if controller is None:
        return ctx
    try:
        if app == WRITER:
            sel = _writer_selection_text(controller)
            ctx.selection_text = sel
            ctx.description = ("selected text" if sel.strip()
                               else "the document text")
        elif app == CALC:
            sel = _calc_selection_text(controller, limit)
            ctx.selection_text = sel
            ctx.description = "selected cells"
        elif app in (IMPRESS, DRAW):
            sel = _draw_selection_text(controller, limit)
            ctx.selection_text = sel
            if not sel.strip():
                sel = _current_page_text(controller, limit)
                ctx.selection_text = sel
                ctx.description = "the current slide/page title"
            else:
                ctx.description = "the selected shape text"
    except Exception:
        pass
    return ctx


def context_prompt_block(ctx, limit=6000):
    """Render DocContext as a prompt fragment for the assistant."""
    if ctx is None or ctx.app == OTHER:
        return ""
    lines = ["", "---", "Document context: LibreOffice %s." % _APP_TITLES.get(ctx.app, "")]
    body = (ctx.selection_text or "").strip()
    if body:
        lines.append("The user is working with %s (content below):" % ctx.description)
        lines.append(truncate(body, limit))
    else:
        lines.append("(no selection)")
    lines.append("---")
    lines.append("Use the context above when relevant; do not repeat it back.")
    return "\n".join(lines)


# --- applying answers ------------------------------------------------------

def _writer_apply(model, text, replace):
    controller = model.getCurrentController()
    cursor = controller.ViewCursor
    text_obj = cursor.getText()
    if replace:
        text_obj.insertString(cursor, text, True)  # True -> replaces selection
    else:
        try:
            cursor.collapseToEnd()
        except Exception:
            pass
        text_obj.insertString(cursor, text, False)
    return True


def _calc_apply(model, text, replace):
    controller = model.getCurrentController()
    target = None
    try:
        sel = controller.getSelection()
        if sel is not None and replace:
            target = sel
    except Exception:
        pass
    if target is None:
        target = controller.ActiveCell
    if target is None:
        return False
    target.setString(text)
    return True


def _draw_apply(model, text, replace):
    controller = model.getCurrentController()
    sel = None
    try:
        sel = controller.getSelection()
    except Exception:
        pass
    for shape in _iter_selected_shapes(sel):
        if hasattr(shape, "getString"):
            try:
                if replace:
                    shape.setString(text)
                else:
                    sh_text = shape.getText()
                    cursor = sh_text.createTextCursor()
                    cursor.gotoEnd(False)
                    sh_text.insertString(cursor, "\n" + text, False)
                return True
            except Exception:
                continue
    # Nothing selected: drop the answer into a new text box on the current page.
    try:
        page = controller.CurrentPage
        import uno  # noqa: F401  (activates the `com` struct namespace)
        from com.sun.star.awt import Size, Point
        shape = model.createInstance("com.sun.star.drawing.TextShape")
        page.add(shape)
        shape.Size = Size(14000, 8000)
        shape.Position = Point(2000, 2000)
        shape.setString(text)
        return True
    except Exception:
        return False


def apply_text(model, text, mode):
    """mode: 'insert' appends at the cursor/selection, 'replace' overwrites it."""
    if model is None or not text:
        return False
    app = detect_app(model)
    replace = (mode == "replace")
    try:
        if app == WRITER:
            return _writer_apply(model, text, replace)
        if app == CALC:
            return _calc_apply(model, text, replace)
        if app in (IMPRESS, DRAW):
            return _draw_apply(model, text, replace)
    except Exception:
        return False
    return False
