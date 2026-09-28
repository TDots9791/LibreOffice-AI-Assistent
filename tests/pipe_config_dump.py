#!/usr/bin/env python3
"""Dump merged /org.openoffice.Office.Addons from a running office via pipe URP."""
import sys
import uno

name = sys.argv[1] if len(sys.argv) > 1 else "loai_pipe"
local = uno.getComponentContext()
resolver = local.ServiceManager.createInstanceWithContext(
    "com.sun.star.bridge.UnoUrlResolver", local)
ctx = resolver.resolve("uno:pipe,name=%s;urp;StarOffice.ComponentContext" % name)
smgr = ctx.ServiceManager
print("CONNECTED")

cp = smgr.createInstanceWithArgumentsAndContext(
    "com.sun.star.configuration.ConfigurationProvider", (), ctx)
node = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
node.Name = "nodepath"
node.Value = "/org.openoffice.Office.Addons"
view = cp.createInstanceWithArguments(
    "com.sun.star.configuration.ConfigurationAccess", (node,))
names = view.getElementNames()
print("AddonUI-level children:", list(names))
try:
    addonui = view.getByName("AddonUI")
    print("AddonUI children:", list(addonui.getElementNames()))
    for setname in ("OfficeMenuBar", "OfficeToolBar"):
        if addonui.hasByName(setname):
            s = addonui.getByName(setname)
            print(setname, "->", list(s.getElementNames()))
        else:
            print(setname, "-> MISSING")
except Exception as exc:
    print("AddonUI read error:", repr(exc))
