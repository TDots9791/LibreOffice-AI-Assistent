"""Static sanity checks for the extension python sources."""
import ast
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
UI = os.path.join(ROOT, "src", "extension", "Scripts", "python",
                  "pythonpath", "lo_ai", "ui")
TARGET = os.path.join(UI, "panel.py")

# getWindow() не существует ни у XControl (диалог), ни у контролов — окно
# берётся через getPeer() (peer-объект реализует XWindow2 → XWindow).
# Регрессия v1.7.0–v1.9.2: 13 вызовов молча падали в try/except.
_NO_GETWINDOW_FILES = ("panel.py", "settings_dialog.py")


def test_panel_self_uppercase_attrs_are_defined():
    tree = ast.parse(open(TARGET, encoding="utf-8").read(), TARGET)
    defined = set()
    used = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for stmt in node.body:
                if isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        if isinstance(t, ast.Name) and t.id.isupper():
                            defined.add(t.id)
        if (isinstance(node, ast.Attribute) and node.attr.isupper()
                and isinstance(node.value, ast.Name)
                and node.value.id == "self"):
            used.add(node.attr)
    missing = used - defined
    assert not missing, ("self.<CONST> used but not defined on the class: %s"
                         % missing)


def test_no_getwindow_calls_on_dialog_or_controls():
    for name in _NO_GETWINDOW_FILES:
        path = os.path.join(UI, name)
        tree = ast.parse(open(path, encoding="utf-8").read(), path)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "getWindow"):
                raise AssertionError(
                    "%s:%d — .getWindow() не существует в AWT; "
                    "использовать getPeer()" % (name, node.lineno))


if __name__ == "__main__":
    test_panel_self_uppercase_attrs_are_defined()
    test_no_getwindow_calls_on_dialog_or_controls()
    print("static OK")
