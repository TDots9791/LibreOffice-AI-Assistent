#!/bin/bash
set -u
export PYTHONPATH=/app/libreoffice/program
PIPE="loai_pipe_$$"
PROFILE=/home/mike/lo-ai-pipe-profile

rm -rf "$PROFILE"
/app/libreoffice/program/soffice.bin \
  -env:UserInstallation="file://$PROFILE" \
  --headless --invisible --norestore --nologo \
  "--accept=pipe,name=$PIPE;urp;" &
OFFPID=$!

python3 - "$PIPE" <<'PYEOF'
import sys, time
import uno
pipe = sys.argv[1]
local = uno.getComponentContext()
resolver = local.ServiceManager.createInstanceWithContext(
    "com.sun.star.bridge.UnoUrlResolver", local)
for attempt in range(60):
    try:
        ctx = resolver.resolve("uno:pipe,name=%s;urp;StarOffice.ComponentContext" % pipe)
        print("CONNECTED on attempt", attempt)
        smgr = ctx.ServiceManager
        cp = smgr.createInstanceWithArgumentsAndContext(
            "com.sun.star.configuration.ConfigurationProvider", (), ctx)
        node = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
        node.Name = "nodepath"
        node.Value = "/org.openoffice.Office.Addons"
        view = cp.createInstanceWithArguments(
            "com.sun.star.configuration.ConfigurationAccess", (node,))
        print("top children:", list(view.getElementNames()))
        addonui = view.getByName("AddonUI")
        print("AddonUI children:", list(addonui.getElementNames()))
        for setname in ("OfficeMenuBar", "OfficeToolBar"):
            if addonui.hasByName(setname):
                s = addonui.getByName(setname)
                print(setname, "->", list(s.getElementNames()))
            else:
                print(setname, "-> MISSING")
        sys.exit(0)
    except Exception as e:
        msg = repr(e)
        if "NoConnectException" in msg or "couldn't connect" in msg:
            time.sleep(0.5)
            continue
        print("FATAL:", msg)
        sys.exit(1)
print("NEVER CONNECTED")
sys.exit(1)
PYEOF
RC=$?
kill $OFFPID 2>/dev/null
exit $RC
