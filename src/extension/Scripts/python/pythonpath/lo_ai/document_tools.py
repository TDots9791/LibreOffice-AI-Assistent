"""Agent tools: read and modify the live document through UNO.

The registry (TOOLS, specs_for_app) is UNO-free so host tests can import it;
`import uno` happens lazily inside the implementations. Every fn(model, args)
runs on the LibreOffice main thread (the agent dispatches via pump.call).
Tool errors are returned as TEXT so the model can correct its arguments.
"""

from .util import truncate

TOOL_RESULT_LIMIT = 4000
MAX_CELLS = 20000

CHART_TYPES = {
    # type -> (diagram service, Vertical for BarDiagram or None)
    "column": ("com.sun.star.chart.BarDiagram", False),
    "bar": ("com.sun.star.chart.BarDiagram", True),
    "line": ("com.sun.star.chart.LineDiagram", None),
    "pie": ("com.sun.star.chart.PieDiagram", None),
    "area": ("com.sun.star.chart.AreaDiagram", None),
    "scatter": ("com.sun.star.chart.XYDiagram", None),
}

_PIVOT_FN = {"sum": "SUM", "count": "COUNT", "countnums": "COUNTNUMS",
             "average": "AVERAGE", "min": "MIN", "max": "MAX",
             "product": "PRODUCT"}


# --- small helpers -----------------------------------------------------------

def _uno():
    import uno
    return uno


def _col_letter(idx):
    """0-based column index -> letters ('A', 'AA', ...)."""
    s = ""
    idx += 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        s = chr(64 + rem + 1) + s
    return s


def _parse_cell(addr):
    """'B3' -> (col, row), 0-based. Raises ValueError on garbage."""
    letters = digits = ""
    for ch in str(addr).strip().upper():
        if ch.isalpha():
            letters += ch
        elif ch.isdigit():
            digits += ch
        else:
            raise ValueError("bad cell address: %r" % addr)
    if not letters or not digits:
        raise ValueError("bad cell address: %r" % addr)
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - 64)
    return col - 1, int(digits) - 1


def _parse_range(rng):
    """'A1:C10' or 'B2' -> (c0, r0, c1, r1), 0-based inclusive."""
    parts = str(rng).strip().split(":")
    if len(parts) == 1:
        c, r = _parse_cell(parts[0])
        return c, r, c, r
    c0, r0 = _parse_cell(parts[0])
    c1, r1 = _parse_cell(parts[1])
    return min(c0, c1), min(r0, r1), max(c0, c1), max(r0, r1)


def _range_dims(rng):
    c0, r0, c1, r1 = _parse_range(rng)
    return c1 - c0 + 1, r1 - r0 + 1


def _sheet(model, name):
    sheets = model.getSheets()
    if not name:
        try:
            return model.getCurrentController().getActiveSheet()
        except Exception:
            return sheets.getByIndex(0)
    if not sheets.hasByName(str(name)):
        raise ValueError("no sheet named %r; available: %s"
                         % (name, ", ".join(sheets.getElementNames())))
    return sheets.getByName(str(name))


def _cellrange(sheet, rng_str):
    cols, rows = _range_dims(rng_str)
    if cols * rows > MAX_CELLS:
        raise ValueError("range %s is too large (%d cells, max %d); "
                         "split it into subranges" % (rng_str, cols * rows,
                                                      MAX_CELLS))
    return sheet.getCellRangeByName(str(rng_str).strip())


def _used_range_string(sheet):
    cur = sheet.createCursor()
    cur.gotoEndOfUsedArea(False)
    a = cur.RangeAddress
    return "%s%d:%s%d" % (_col_letter(a.StartColumn), a.StartRow + 1,
                          _col_letter(a.EndColumn), a.EndRow + 1)


def _color(value):
    return int(str(value).lstrip("#"), 16)


def _num_like(s):
    """True when a string should become a number cell (not dates/phones)."""
    t = s.strip()
    if not t or t.lower() in ("nan", "inf", "-inf", "infinity"):
        return False
    try:
        float(t.replace(",", "."))
        return True
    except ValueError:
        return False


# --- Calc tools ---------------------------------------------------------------

def calc_info(model, args):
    sheets = model.getSheets()
    lines = ["Sheets: " + ", ".join(sheets.getElementNames())]
    try:
        lines.append("Active sheet: %s"
                     % model.getCurrentController().getActiveSheet().getName())
    except Exception:
        pass
    for i in range(sheets.Count):
        sh = sheets.getByIndex(i)
        try:
            lines.append("%s: used range %s" % (sh.getName(),
                                                _used_range_string(sh)))
        except Exception:
            lines.append("%s: (used range unavailable)" % sh.getName())
    return "\n".join(lines)


def read_range(model, args):
    sheet = _sheet(model, args.get("sheet"))
    rng_str = str(args.get("range") or "").strip()
    if not rng_str:
        raise ValueError("parameter 'range' is required (e.g. \"A1:F30\")")
    rng = _cellrange(sheet, rng_str)
    data = rng.getDataArray()
    try:
        max_rows = max(1, int(args.get("max_rows") or 200))
    except (TypeError, ValueError):
        max_rows = 200
    lines = ["%s!%s: %d rows x %d cols (values)"
             % (sheet.getName(), rng_str.upper(), len(data),
                len(data[0]) if data else 0)]
    for row in data[:max_rows]:
        lines.append(" | ".join("" if v is None else str(v) for v in row))
    if len(data) > max_rows:
        lines.append("… (%d more rows not shown; raise max_rows or read "
                     "subranges)" % (len(data) - max_rows))
    if args.get("formulas"):
        lines.append("Formulas in the same range:")
        for row in rng.getFormulaArray()[:max_rows]:
            lines.append(" | ".join("" if v is None else str(v) for v in row))
    return "\n".join(lines)


def _coerce_cell(v):
    if v is None or v == "":
        return ""
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if _num_like(s):
        return float(s.replace(",", "."))
    return s


def write_range(model, args):
    sheet = _sheet(model, args.get("sheet"))
    rng_str = str(args.get("range") or "").strip()
    values = args.get("values")
    if not isinstance(values, (list, tuple)) or not values:
        raise ValueError("parameter 'values' must be a non-empty 2D array, "
                         "e.g. [[\"Name\", 12], [\"Qty\", 3]]")
    cols, rows = _range_dims(rng_str)
    if len(values) != rows or any(not isinstance(r, (list, tuple))
                                  or len(r) != cols for r in values):
        raise ValueError("values shape (%d rows x %s cols) must match range "
                         "%s (%d rows x %d cols)"
                         % (len(values),
                            len(values[0]) if values else 0,
                            rng_str.upper(), rows, cols))
    rng = sheet.getCellRangeByName(rng_str)
    rng.setDataArray(tuple(tuple(_coerce_cell(v) for v in row)
                           for row in values))
    return "Wrote %d rows x %d cols to %s!%s" % (rows, cols, sheet.getName(),
                                                 rng_str.upper())


def set_formula(model, args):
    sheet = _sheet(model, args.get("sheet"))
    rng_str = str(args.get("range") or "").strip()
    formulas = args.get("formulas")
    rng = _cellrange(sheet, rng_str)
    cols, rows = _range_dims(rng_str)
    if isinstance(formulas, str):
        formulas = [[formulas]]
    if not isinstance(formulas, (list, tuple)) or not formulas:
        raise ValueError("parameter 'formulas' must be a string (single cell) "
                         "or a 2D array matching the range")
    if len(formulas) != rows or any(not isinstance(r, (list, tuple))
                                    or len(r) != cols for r in formulas):
        raise ValueError("formulas shape (%d rows) must match range %s "
                         "(%d rows x %d cols)"
                         % (len(formulas), rng_str.upper(), rows, cols))
    n = 0
    for r in range(rows):
        for c in range(cols):
            f = formulas[r][c]
            if f is None or f == "":
                continue
            rng.getCellByPosition(c, r).setFormula(str(f))
            n += 1
    return "Set %d formula(s) in %s!%s" % (n, sheet.getName(), rng_str.upper())


def sort_range(model, args):
    sheet = _sheet(model, args.get("sheet"))
    rng_str = str(args.get("range") or "").strip()
    keys = args.get("keys")
    if not keys:
        raise ValueError("parameter 'keys' is required, e.g. "
                         "[{\"column\": \"B\", \"ascending\": true}]")
    rng = _cellrange(sheet, rng_str)
    c0, _r0, _c1, _r1 = _parse_range(rng_str)
    uno = _uno()
    fields = []
    for k in keys:
        col, _row = _parse_cell("%s1" % k.get("column"))
        f = uno.createUnoStruct("com.sun.star.table.TableSortField")
        f.Field = col - c0
        f.IsAscending = bool(k.get("ascending", True))
        fields.append(f)
    typed = uno.Any("[]com.sun.star.table.TableSortField", tuple(fields))
    desc = rng.createSortDescriptor()
    for p in desc:
        if p.Name == "ContainsHeader":
            p.Value = bool(args.get("has_header", False))
        elif p.Name == "SortFields":
            p.Value = typed
    rng.sort(tuple(desc))
    return "Sorted %s!%s by %s" % (sheet.getName(), rng_str.upper(),
                                   ", ".join(str(k.get("column")) for k in keys))


def format_range(model, args):
    sheet = _sheet(model, args.get("sheet"))
    rng_str = str(args.get("range") or "").strip()
    rng = _cellrange(sheet, rng_str)
    uno = _uno()
    done = []
    if "bold" in args and args["bold"] is not None:
        rng.CharWeight = 150.0 if args["bold"] else 100.0
        done.append("bold=%s" % args["bold"])
    if "italic" in args and args["italic"] is not None:
        rng.CharPosture = uno.Enum("com.sun.star.awt.FontSlant",
                                   "ITALIC" if args["italic"] else "NONE")
        done.append("italic=%s" % args["italic"])
    if args.get("bg_color"):
        rng.CellBackColor = _color(args["bg_color"])
        done.append("bg=#%s" % str(args["bg_color"]).lstrip("#"))
    if args.get("font_color"):
        rng.CharColor = _color(args["font_color"])
        done.append("font=#%s" % str(args["font_color"]).lstrip("#"))
    if args.get("number_format"):
        fmt = str(args["number_format"])
        formats = model.getNumberFormats()
        loc = uno.createUnoStruct("com.sun.star.lang.Locale")
        key = formats.queryKey(fmt, loc, False)
        if key == -1:
            key = formats.addNew(fmt, loc)
        rng.NumberFormat = key
        done.append("numfmt=%s" % fmt)
    if not done:
        raise ValueError("nothing to apply: pass bold/italic/bg_color/"
                         "font_color/number_format")
    return "Formatted %s!%s: %s" % (sheet.getName(), rng_str.upper(),
                                    ", ".join(done))


def create_chart(model, args):
    sheet = _sheet(model, args.get("sheet"))
    data_range = str(args.get("data_range") or "").strip()
    if not data_range:
        raise ValueError("parameter 'data_range' is required (e.g. \"A1:C30\")")
    ctype = str(args.get("chart_type") or "column").lower()
    if ctype not in CHART_TYPES:
        raise ValueError("chart_type must be one of: %s"
                         % ", ".join(sorted(CHART_TYPES)))
    rng = _cellrange(sheet, data_range)
    uno = _uno()
    rect = uno.createUnoStruct("com.sun.star.awt.Rectangle")
    pos = str(args.get("position_cell") or "").strip()
    if pos:
        point = sheet.getCellRangeByName(pos).getPosition()
        rect.X, rect.Y = point.X, point.Y
    else:
        rect.X, rect.Y = 15500, 500
    rect.Width, rect.Height = 10000, 8000
    charts = sheet.getCharts()
    name = "AIChart_%d" % (int(__import__("time").time()) % 100000000)
    charts.addNewByName(name, rect, (rng.getRangeAddress(),), True, True)
    doc = charts.getByName(name).getEmbeddedObject()
    service, vertical = CHART_TYPES[ctype]
    doc.setDiagram(doc.createInstance(service))
    if vertical is not None:
        doc.getDiagram().Vertical = vertical
    title = str(args.get("title") or "").strip()
    if title:
        doc.HasMainTitle = True
        doc.Title.String = title
    return "Created %s chart '%s' on %s from %s%s" % (
        ctype, name, sheet.getName(), data_range.upper(),
        " with title %r" % title if title else "")


def create_pivot(model, args):
    src_sheet = _sheet(model, args.get("source_sheet"))
    source_range = str(args.get("source_range") or "").strip()
    if not source_range:
        raise ValueError("parameter 'source_range' is required (e.g. \"A1:F30\")")
    row_fields = [str(f) for f in (args.get("row_fields") or [])]
    col_fields = [str(f) for f in (args.get("col_fields") or [])]
    data_fields = args.get("data_fields") or []
    if not row_fields and not col_fields and not data_fields:
        raise ValueError("pass at least one of row_fields/col_fields/"
                         "data_fields")
    src = _cellrange(src_sheet, source_range)
    sheets = model.getSheets()
    tname = str(args.get("target_sheet") or "Pivot")
    if not sheets.hasByName(tname):
        sheets.insertNewByName(tname, sheets.Count)
    tsheet = sheets.getByName(tname)
    uno = _uno()
    dp = tsheet.getDataPilotTables()
    desc = dp.createDataPilotDescriptor()
    desc.setSourceRange(src.getRangeAddress())
    fields = desc.getDataPilotFields()
    for i in range(fields.Count):
        f = fields.getByIndex(i)
        nm = f.getName() if hasattr(f, "getName") else f.Name
        if nm in row_fields:
            f.Orientation = uno.Enum(
                "com.sun.star.sheet.DataPilotFieldOrientation", "ROW")
        elif nm in col_fields:
            f.Orientation = uno.Enum(
                "com.sun.star.sheet.DataPilotFieldOrientation", "COLUMN")
        else:
            spec = next((d for d in data_fields
                         if str(d.get("field")) == nm), None)
            if spec is not None:
                f.Orientation = uno.Enum(
                    "com.sun.star.sheet.DataPilotFieldOrientation", "DATA")
                fn = str(spec.get("function") or "sum").lower()
                if fn not in _PIVOT_FN:
                    raise ValueError("unknown function %r for field %r; use: %s"
                                     % (spec.get("function"), nm,
                                        ", ".join(sorted(_PIVOT_FN))))
                f.Function = uno.Enum("com.sun.star.sheet.GeneralFunction",
                                      _PIVOT_FN[fn])
    target_cell = str(args.get("target_cell") or "A1")
    cell = tsheet.getCellRangeByName(target_cell)
    name = "AIPivot_%d" % (int(__import__("time").time()) % 100000000)
    dp.insertNewByName(name, cell.getCellAddress(), desc)
    return ("Pivot '%s' created on sheet %s at %s (rows: %s; cols: %s; "
            "data: %s)" % (name, tname, target_cell.upper(),
                           row_fields or "-", col_fields or "-",
                           ["%s(%s)" % (d.get("field"), d.get("function", "sum"))
                            for d in data_fields] or "-"))


def find_replace_calc(model, args):
    find = str(args.get("find") or "")
    if not find:
        raise ValueError("parameter 'find' is required")
    replace = str(args.get("replace") or "")
    sheets = model.getSheets()
    if args.get("all_sheets"):
        targets = [sheets.getByIndex(i) for i in range(sheets.Count)]
    else:
        targets = [_sheet(model, args.get("sheet"))]
    total = 0
    for sh in targets:
        desc = sh.createReplaceDescriptor()
        desc.SearchString = find
        desc.ReplaceString = replace
        total += sh.replaceAll(desc)
    return "Replaced %d occurrence(s) of %r with %r" % (total, find, replace)


# --- Writer tools --------------------------------------------------------------

def writer_info(model, args):
    text = model.getText()
    paras = 0
    chars = 0
    en = text.createEnumeration()
    while en.hasMoreElements():
        el = en.nextElement()
        try:
            paras += 1
            chars += len(el.getString() or "")
        except Exception:
            continue
        if paras > 20000:
            break
    try:
        tables = model.getTextTables().Count
    except Exception:
        tables = 0
    return ("Writer document: %d paragraphs, %d characters, %d table(s)"
            % (paras, chars, tables))


def read_document(model, args):
    try:
        max_chars = max(500, int(args.get("max_chars") or 12000))
    except (TypeError, ValueError):
        max_chars = 12000
    text = model.getText().getString()
    if not text.strip():
        return "(the document is empty)"
    return truncate("Total characters: %d\n\n%s" % (len(text), text),
                    max_chars)


def read_selection(model, args):
    sel = model.getCurrentController().ViewCursor.getString()
    if not (sel or "").strip():
        return "(no selection — the cursor is placed; use read_document)"
    return "Selection (%d chars):\n%s" % (len(sel), sel)


def replace_selection(model, args):
    text = str(args.get("text") or "")
    cursor = model.getCurrentController().ViewCursor
    cursor.getText().insertString(cursor, text, True)  # True -> replaces
    return "Selection replaced with %d characters." % len(text)


def insert_at_cursor(model, args):
    text = str(args.get("text") or "")
    cursor = model.getCurrentController().ViewCursor
    try:
        cursor.collapseToEnd()
    except Exception:
        pass
    cursor.getText().insertString(cursor, text, False)
    return "Inserted %d characters at the cursor." % len(text)


def writer_find_replace(model, args):
    find = str(args.get("find") or "")
    if not find:
        raise ValueError("parameter 'find' is required")
    replace = str(args.get("replace") or "")
    desc = model.createReplaceDescriptor()
    desc.SearchString = find
    desc.ReplaceString = replace
    count = model.replaceAll(desc)
    return "Replaced %d occurrence(s) of %r with %r" % (count, find, replace)


# --- registry -------------------------------------------------------------------

def _schema(props, required=None):
    return {"type": "object", "properties": props,
            "required": required or []}


def _t(name, app, description, parameters, required, fn=None):
    """Two call forms: _t(n, a, d, schema, fn) or _t(n, a, d, schema,
    [required...], fn) — required goes into the JSON schema."""
    if fn is None:
        fn, required = required, None
    if required:
        parameters = dict(parameters)
        parameters["required"] = list(required)
    return {"name": name, "app": app, "description": description,
            "parameters": parameters, "fn": fn}


CALC_SHEET = {"type": "string", "description": "Sheet name; omit = active sheet."}

TOOLS = [
    _t("calc_info", "calc",
       "List sheets of the spreadsheet and their used ranges.",
       _schema({}), calc_info),
    _t("read_range", "calc",
       "Read cell values (and optionally formulas) of a range.",
       _schema({"sheet": CALC_SHEET,
                "range": {"type": "string",
                          "description": "Range like \"A1:F30\"."},
                "formulas": {"type": "boolean",
                             "description": "Also return formulas."},
                "max_rows": {"type": "integer",
                             "description": "Rows to show (default 200)."}}),
       ["range"], read_range),
    _t("write_range", "calc",
       "Write a 2D array of values into a range (numbers/strings).",
       _schema({"sheet": CALC_SHEET,
                "range": {"type": "string"},
                "values": {"type": "array", "items": {"type": "array"},
                           "description": "2D array matching the range shape, "
                                          "e.g. [[\"Name\", 12], [\"Qty\", 3]]."}}),
       ["range", "values"], write_range),
    _t("set_formula", "calc",
       "Put formulas into a range (2D array of formula strings) or one cell.",
       _schema({"sheet": CALC_SHEET,
                "range": {"type": "string"},
                "formulas": {"type": "array",
                             "items": {"type": "array"},
                             "description": "2D array like "
                                            "[[\"=SUM(B2:B10)\"]]."}}),
       ["range", "formulas"], set_formula),
    _t("sort_range", "calc",
       "Sort a range.",
       _schema({"sheet": CALC_SHEET,
                "range": {"type": "string"},
                "has_header": {"type": "boolean"},
                "keys": {"type": "array",
                         "description": "e.g. [{\"column\": \"B\", "
                                        "\"ascending\": true}].",
                         "items": {"type": "object"}}}),
       ["range", "keys"], sort_range),
    _t("format_range", "calc",
       "Format a range: bold, italic, background/font color (hex), "
       "number format string.",
       _schema({"sheet": CALC_SHEET,
                "range": {"type": "string"},
                "bold": {"type": "boolean"},
                "italic": {"type": "boolean"},
                "bg_color": {"type": "string", "description": "e.g. \"FFE082\"."},
                "font_color": {"type": "string"},
                "number_format": {"type": "string",
                                  "description": "e.g. \"0.00%\", \"#,##0.00\"."}}),
       ["range"], format_range),
    _t("create_chart", "calc",
       "Create a chart from a data range. Types: column, bar, line, pie, "
       "area, scatter.",
       _schema({"sheet": CALC_SHEET,
                "data_range": {"type": "string"},
                "chart_type": {"type": "string"},
                "title": {"type": "string"},
                "position_cell": {"type": "string",
                                  "description": "Cell for the chart's top-left "
                                                 "corner, e.g. \"H2\"."}}),
       ["data_range"], create_chart),
    _t("create_pivot", "calc",
       "Create a pivot (DataPilot) table into a new or existing sheet.",
       _schema({"source_sheet": CALC_SHEET,
                "source_range": {"type": "string"},
                "row_fields": {"type": "array", "items": {"type": "string"}},
                "col_fields": {"type": "array", "items": {"type": "string"}},
                "data_fields": {"type": "array",
                                "description": "e.g. [{\"field\": \"Sales\", "
                                               "\"function\": \"sum\"}]; "
                                               "functions: sum, count, average, "
                                               "min, max, product.",
                                "items": {"type": "object"}},
                "target_sheet": {"type": "string"},
                "target_cell": {"type": "string"}}),
       ["source_range"], create_pivot),
    _t("find_replace", "calc",
       "Find and replace text in cells (active sheet or all sheets).",
       _schema({"sheet": CALC_SHEET,
                "find": {"type": "string"},
                "replace": {"type": "string"},
                "all_sheets": {"type": "boolean"}}),
       ["find"], find_replace_calc),

    _t("writer_info", "writer",
       "Document statistics (paragraphs, characters, tables).",
       _schema({}), writer_info),
    _t("read_document", "writer",
       "Read the full text of the document.",
       _schema({"max_chars": {"type": "integer",
                              "description": "Limit (default 12000)."}}),
       read_document),
    _t("read_selection", "writer",
       "Read the currently selected text.",
       _schema({}), read_selection),
    _t("replace_selection", "writer",
       "Overwrite the current selection with new text.",
       _schema({"text": {"type": "string"}}), ["text"], replace_selection),
    _t("insert_at_cursor", "writer",
       "Insert text at the cursor position.",
       _schema({"text": {"type": "string"}}), ["text"], insert_at_cursor),
    _t("writer_find_replace", "writer",
       "Find and replace across the whole document.",
       _schema({"find": {"type": "string"},
                "replace": {"type": "string"}}),
       ["find"], writer_find_replace),
]

_BY_NAME = {t["name"]: t for t in TOOLS}


def specs_for_app(app):
    """Tool specs (OpenAI function schema payloads) for a document type."""
    return [{"name": t["name"], "description": t["description"],
             "parameters": t["parameters"]}
            for t in TOOLS if t["app"] == app]


def execute(model, app, name, args):
    """Run one tool; returns a text result (never raises)."""
    tool = _BY_NAME.get(name)
    if tool is None:
        return "ERROR: unknown tool %r; available: %s" % (
            name, ", ".join(sorted(t["name"] for t in TOOLS)))
    if tool["app"] != app:
        return "ERROR: tool %r works on %s documents, not %s" % (
            name, tool["app"], app)
    if isinstance(args, str):
        import json
        try:
            args = json.loads(args or "{}")
        except ValueError as exc:
            return "ERROR: arguments are not valid JSON (%s); send a JSON " \
                   "object" % exc
    if not isinstance(args, dict):
        return "ERROR: arguments must be a JSON object"
    for req in _required_of(tool):
        if req not in args:
            return "ERROR: missing required parameter %r" % req
    try:
        return truncate(str(tool["fn"](model, args)), TOOL_RESULT_LIMIT)
    except Exception as exc:
        return "ERROR: %s" % (exc,)


def _required_of(tool):
    try:
        return tool["parameters"].get("required") or []
    except AttributeError:
        return []
