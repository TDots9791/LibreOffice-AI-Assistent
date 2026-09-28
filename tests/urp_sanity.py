#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Minimal URP sanity: connect, do trivial calls with pauses, report each step."""
import os
import sys
import time

import uno

PORT = os.environ.get("LOAI_PORT", "2004")

local = uno.getComponentContext()
resolver = local.ServiceManager.createInstanceWithContext(
    "com.sun.star.bridge.UnoUrlResolver", local)

for attempt in range(3):
    try:
        print("resolving...")
        ctx = resolver.resolve(
            "uno:socket,host=127.0.0.1,port=%s;urp;StarOffice.ComponentContext" % PORT)
        print("resolve OK")
        smgr = ctx.ServiceManager
        print("smgr OK:", smgr is not None)
        time.sleep(0.3)
        desktop = smgr.createInstance("com.sun.star.frame.Desktop")
        print("desktop OK:", desktop is not None)
        time.sleep(0.3)
        print("impl:", desktop.getImplementationName())
        time.sleep(0.3)
        ps = smgr.createInstance("com.sun.star.util.PathSettings")
        print("UserConfig:", ps.getPropertyValue("UserConfig"))
        print("SANITY OK")
        sys.exit(0)
    except Exception as exc:
        print("attempt %d FAIL: %r" % (attempt, exc))
        time.sleep(2)
sys.exit(1)
